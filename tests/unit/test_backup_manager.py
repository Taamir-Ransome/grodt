"""
Unit tests for backup manager functionality.

Tests backup creation, restoration, integrity verification, and retention policies.
"""

import asyncio
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from grodtd.storage.backup_manager import (
    BackupManager,
    BackupMetadata,
    BackupConfig,
    BackupScheduler,
    create_backup_manager,
    create_backup_scheduler
)


class TestBackupManager(unittest.TestCase):
    """Test cases for BackupManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test.db"
        self.test_config_path = Path(self.temp_dir) / "backup_config.yaml"
        self.test_backup_dir = Path(self.temp_dir) / "backups"
        
        # Create test database with sample data
        self._create_test_database()
        
        # Create test configuration
        self._create_test_config()
        
        # Initialize backup manager
        self.backup_manager = BackupManager(
            str(self.test_config_path),
            str(self.test_db_path)
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_database(self):
        """Create test database with sample data."""
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY,
                    timestamp DATETIME,
                    symbol TEXT,
                    side TEXT,
                    price REAL,
                    quantity REAL
                )
            """)
            
            # Create orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY,
                    client_order_id TEXT,
                    status TEXT,
                    symbol TEXT,
                    quantity REAL,
                    submit_timestamp DATETIME,
                    fill_timestamp DATETIME
                )
            """)
            
            # Create positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    quantity REAL,
                    average_entry_price REAL
                )
            """)
            
            # Create equity_curve table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS equity_curve (
                    timestamp DATETIME PRIMARY KEY,
                    portfolio_value REAL
                )
            """)
            
            # Insert sample data
            cursor.execute("""
                INSERT INTO trades (timestamp, symbol, side, price, quantity)
                VALUES 
                    ('2024-01-01 10:00:00', 'BTC', 'buy', 50000.0, 0.1),
                    ('2024-01-01 11:00:00', 'ETH', 'sell', 3000.0, 1.0)
            """)
            
            cursor.execute("""
                INSERT INTO orders (client_order_id, status, symbol, quantity, submit_timestamp)
                VALUES 
                    ('order_1', 'filled', 'BTC', 0.1, '2024-01-01 10:00:00'),
                    ('order_2', 'filled', 'ETH', 1.0, '2024-01-01 11:00:00')
            """)
            
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, average_entry_price)
                VALUES 
                    ('BTC', 0.1, 50000.0),
                    ('ETH', -1.0, 3000.0)
            """)
            
            cursor.execute("""
                INSERT INTO equity_curve (timestamp, portfolio_value)
                VALUES 
                    ('2024-01-01 10:00:00', 10000.0),
                    ('2024-01-01 11:00:00', 10200.0)
            """)
            
            conn.commit()
    
    def _create_test_config(self):
        """Create test configuration file."""
        config_data = {
            'backup_directory': str(self.test_backup_dir),
            'retention_days': 7,
            'retention_weeks': 4,
            'retention_months': 12,
            'retention_years': 3,
            'compression': 'snappy',
            'backup_time': '02:00',
            'enabled': True,
            'tables_to_backup': ['trades', 'orders', 'positions', 'equity_curve'],
            'verify_integrity': True,
            'max_backup_size_mb': 1000
        }
        
        import yaml
        with open(self.test_config_path, 'w') as f:
            yaml.dump(config_data, f)
    
    @pytest.mark.asyncio
    async def test_create_backup(self):
        """Test backup creation."""
        backup_metadata = await self.backup_manager.create_backup()
        
        # Verify backup was created
        self.assertEqual(backup_metadata.status, 'success')
        self.assertGreater(len(backup_metadata.tables_backed_up), 0)
        self.assertGreater(backup_metadata.total_records, 0)
        self.assertGreater(backup_metadata.backup_size_bytes, 0)
        
        # Verify backup files exist
        backup_path = self.test_backup_dir / backup_metadata.backup_id
        self.assertTrue(backup_path.exists())
        
        for table_name in backup_metadata.tables_backed_up:
            parquet_file = backup_path / f"{table_name}.parquet"
            self.assertTrue(parquet_file.exists())
    
    @pytest.mark.asyncio
    async def test_backup_integrity_verification(self):
        """Test backup integrity verification."""
        backup_metadata = await self.backup_manager.create_backup()
        
        # Verify integrity check passes
        backup_path = self.test_backup_dir / backup_metadata.backup_id
        integrity_result = await self.backup_manager._verify_backup_integrity(
            backup_path, backup_metadata
        )
        self.assertTrue(integrity_result)
    
    @pytest.mark.asyncio
    async def test_restore_backup(self):
        """Test backup restoration."""
        # Create backup
        backup_metadata = await self.backup_manager.create_backup()
        
        # Create new database for restoration
        restore_db_path = Path(self.temp_dir) / "restore.db"
        
        # Restore backup
        restore_success = await self.backup_manager.restore_backup(
            backup_metadata.backup_id, str(restore_db_path)
        )
        self.assertTrue(restore_success)
        
        # Verify restored data
        with sqlite3.connect(restore_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            trade_count = cursor.fetchone()[0]
            self.assertEqual(trade_count, 2)
            
            cursor.execute("SELECT COUNT(*) FROM orders")
            order_count = cursor.fetchone()[0]
            self.assertEqual(order_count, 2)
    
    def test_get_database_stats(self):
        """Test database statistics retrieval."""
        stats = self.backup_manager._get_database_stats()
        
        self.assertIn('trades', stats)
        self.assertIn('orders', stats)
        self.assertIn('positions', stats)
        self.assertIn('equity_curve', stats)
        
        self.assertEqual(stats['trades'], 2)
        self.assertEqual(stats['orders'], 2)
        self.assertEqual(stats['positions'], 2)
        self.assertEqual(stats['equity_curve'], 2)
    
    def test_calculate_backup_checksum(self):
        """Test backup checksum calculation."""
        # Create a test backup directory
        test_backup_path = self.test_backup_dir / "test_backup"
        test_backup_path.mkdir(parents=True, exist_ok=True)
        
        # Create test files
        (test_backup_path / "test1.txt").write_text("test content 1")
        (test_backup_path / "test2.txt").write_text("test content 2")
        
        # Calculate checksum
        checksum = self.backup_manager._calculate_backup_checksum(test_backup_path)
        
        # Verify checksum is not empty
        self.assertIsNotNone(checksum)
        self.assertEqual(len(checksum), 64)  # SHA256 hex length
    
    def test_optimize_dataframe_types(self):
        """Test DataFrame type optimization."""
        # Create test DataFrame
        df = pd.DataFrame({
            'int_col': [1, 2, 3],
            'float_col': [1.1, 2.2, 3.3],
            'string_col': ['a', 'b', 'c']
        })
        
        # Optimize types
        optimized_df = self.backup_manager._optimize_dataframe_types(df)
        
        # Verify optimization (pandas downcasting behavior may vary)
        self.assertIn(optimized_df['int_col'].dtype, ['int8', 'int16', 'int32', 'int64'])
        self.assertIn(optimized_df['float_col'].dtype, ['float32', 'float64'])
        self.assertEqual(optimized_df['string_col'].dtype, 'string')  # String type
    
    def test_get_backup_status(self):
        """Test backup status retrieval."""
        status = self.backup_manager.get_backup_status()
        
        self.assertIn('backup_directory', status)
        self.assertIn('total_backups', status)
        self.assertIn('total_size_mb', status)
        self.assertIn('config', status)
        
        self.assertEqual(status['total_backups'], 0)  # No backups yet
        self.assertEqual(status['config']['enabled'], True)
    
    def test_list_backups(self):
        """Test backup listing."""
        backups = self.backup_manager.list_backups()
        
        # Should be empty initially
        self.assertEqual(len(backups), 0)
    
    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self):
        """Test backup cleanup functionality."""
        # Create multiple test backups with different ages
        old_backup_id = "old_backup"
        recent_backup_id = "recent_backup"
        
        # Create old backup (simulate by setting timestamp)
        old_backup_path = self.test_backup_dir / old_backup_id
        old_backup_path.mkdir(parents=True, exist_ok=True)
        
        old_metadata = BackupMetadata(
            backup_id=old_backup_id,
            timestamp=datetime.now() - timedelta(days=10),  # 10 days old
            tables_backed_up=['trades'],
            total_records=1,
            backup_size_bytes=1000,
            compression_ratio=0.5,
            checksum='test_checksum',
            status='success'
        )
        
        self.backup_manager._save_backup_metadata(old_backup_path, old_metadata)
        
        # Create recent backup
        recent_backup_path = self.test_backup_dir / recent_backup_id
        recent_backup_path.mkdir(parents=True, exist_ok=True)
        
        recent_metadata = BackupMetadata(
            backup_id=recent_backup_id,
            timestamp=datetime.now() - timedelta(days=1),  # 1 day old
            tables_backed_up=['trades'],
            total_records=1,
            backup_size_bytes=1000,
            compression_ratio=0.5,
            checksum='test_checksum',
            status='success'
        )
        
        self.backup_manager._save_backup_metadata(recent_backup_path, recent_metadata)
        
        # Run cleanup
        await self.backup_manager.cleanup_old_backups()
        
        # Verify old backup was removed, recent backup remains
        self.assertFalse(old_backup_path.exists())
        self.assertTrue(recent_backup_path.exists())


class TestBackupScheduler(unittest.TestCase):
    """Test cases for BackupScheduler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "test.db"
        self.test_config_path = Path(self.temp_dir) / "backup_config.yaml"
        
        # Create test database
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE test (id INTEGER)")
            conn.commit()
        
        # Create test configuration
        import yaml
        config_data = {
            'backup_directory': str(Path(self.temp_dir) / "backups"),
            'retention_days': 7,
            'retention_weeks': 4,
            'retention_months': 12,
            'retention_years': 3,
            'compression': 'snappy',
            'backup_time': '02:00',
            'enabled': True,
            'tables_to_backup': ['test'],
            'verify_integrity': True,
            'max_backup_size_mb': 1000
        }
        
        with open(self.test_config_path, 'w') as f:
            yaml.dump(config_data, f)
        
        # Create backup manager and scheduler
        self.backup_manager = BackupManager(
            str(self.test_config_path),
            str(self.test_db_path)
        )
        self.scheduler = BackupScheduler(self.backup_manager)
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_should_run_backup(self):
        """Test backup scheduling logic."""
        # Test with current time matching backup time
        with patch('grodtd.storage.backup_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 2, 30)  # 2:30 AM
            mock_datetime.fromtimestamp.return_value = datetime(2024, 1, 1, 2, 30)
            
            result = self.scheduler._should_run_backup()
            self.assertTrue(result)
    
    def test_should_not_run_backup_wrong_time(self):
        """Test backup scheduling with wrong time."""
        with patch('grodtd.storage.backup_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 10, 0)  # 10:00 AM
            mock_datetime.fromtimestamp.return_value = datetime(2024, 1, 1, 10, 0)
            
            result = self.scheduler._should_run_backup()
            self.assertFalse(result)
    
    def test_should_not_run_backup_disabled(self):
        """Test backup scheduling when disabled."""
        self.backup_manager.config.enabled = False
        
        with patch('grodtd.storage.backup_manager.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 2, 30)  # 2:30 AM
            mock_datetime.fromtimestamp.return_value = datetime(2024, 1, 1, 2, 30)
            
            result = self.scheduler._should_run_backup()
            self.assertFalse(result)


class TestBackupConfig(unittest.TestCase):
    """Test cases for BackupConfig class."""
    
    def test_backup_config_creation(self):
        """Test BackupConfig creation."""
        config = BackupConfig(
            backup_directory="test/backups",
            retention_days=7,
            retention_weeks=4,
            retention_months=12,
            retention_years=3,
            compression="snappy",
            backup_time="02:00",
            enabled=True,
            tables_to_backup=["trades", "orders"],
            verify_integrity=True,
            max_backup_size_mb=1000
        )
        
        self.assertEqual(config.backup_directory, "test/backups")
        self.assertEqual(config.retention_days, 7)
        self.assertEqual(config.compression, "snappy")
        self.assertTrue(config.enabled)


class TestBackupMetadata(unittest.TestCase):
    """Test cases for BackupMetadata class."""
    
    def test_backup_metadata_creation(self):
        """Test BackupMetadata creation."""
        metadata = BackupMetadata(
            backup_id="test_backup",
            timestamp=datetime.now(),
            tables_backed_up=["trades"],
            total_records=100,
            backup_size_bytes=1000,
            compression_ratio=0.5,
            checksum="test_checksum",
            status="success"
        )
        
        self.assertEqual(metadata.backup_id, "test_backup")
        self.assertEqual(metadata.total_records, 100)
        self.assertEqual(metadata.status, "success")


class TestFactoryFunctions(unittest.TestCase):
    """Test cases for factory functions."""
    
    def test_create_backup_manager(self):
        """Test backup manager factory function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            db_path = Path(temp_dir) / "test.db"
            
            # Create minimal config
            import yaml
            config_data = {
                'backup_directory': str(Path(temp_dir) / "backups"),
                'retention_days': 7,
                'retention_weeks': 4,
                'retention_months': 12,
                'retention_years': 3,
                'compression': 'snappy',
                'backup_time': '02:00',
                'enabled': True,
                'tables_to_backup': ['test'],
                'verify_integrity': True,
                'max_backup_size_mb': 1000
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
            
            # Create test database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE test (id INTEGER)")
                conn.commit()
            
            # Create backup manager
            backup_manager = create_backup_manager(str(config_path), str(db_path))
            
            self.assertIsInstance(backup_manager, BackupManager)
    
    def test_create_backup_scheduler(self):
        """Test backup scheduler factory function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            db_path = Path(temp_dir) / "test.db"
            
            # Create minimal config
            import yaml
            config_data = {
                'backup_directory': str(Path(temp_dir) / "backups"),
                'retention_days': 7,
                'retention_weeks': 4,
                'retention_months': 12,
                'retention_years': 3,
                'compression': 'snappy',
                'backup_time': '02:00',
                'enabled': True,
                'tables_to_backup': ['test'],
                'verify_integrity': True,
                'max_backup_size_mb': 1000
            }
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f)
            
            # Create test database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE test (id INTEGER)")
                conn.commit()
            
            # Create backup manager and scheduler
            backup_manager = create_backup_manager(str(config_path), str(db_path))
            scheduler = create_backup_scheduler(backup_manager)
            
            self.assertIsInstance(scheduler, BackupScheduler)


if __name__ == '__main__':
    unittest.main()
