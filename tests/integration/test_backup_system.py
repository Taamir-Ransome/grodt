"""
Integration tests for backup system.

Tests end-to-end backup and restoration workflows, performance,
and failure scenarios.
"""

import asyncio
import json
import os
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from grodtd.storage.backup_manager import (
    BackupManager,
    BackupScheduler,
    create_backup_manager,
    create_backup_scheduler
)


class TestBackupSystemIntegration(unittest.TestCase):
    """Integration tests for complete backup system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_db_path = Path(self.temp_dir) / "integration_test.db"
        self.test_config_path = Path(self.temp_dir) / "backup_config.yaml"
        self.test_backup_dir = Path(self.temp_dir) / "backups"
        
        # Create comprehensive test database
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
        """Create comprehensive test database with realistic data."""
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            
            # Create trades table with realistic schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    commission REAL DEFAULT 0.0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create orders table with realistic schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_order_id TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL,
                    submit_timestamp DATETIME NOT NULL,
                    fill_timestamp DATETIME,
                    cancel_timestamp DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create positions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    symbol TEXT PRIMARY KEY,
                    quantity REAL NOT NULL,
                    average_entry_price REAL NOT NULL,
                    current_price REAL,
                    unrealized_pnl REAL DEFAULT 0.0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create equity_curve table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS equity_curve (
                    timestamp DATETIME PRIMARY KEY,
                    portfolio_value REAL NOT NULL,
                    cash_balance REAL NOT NULL,
                    total_pnl REAL DEFAULT 0.0,
                    daily_pnl REAL DEFAULT 0.0
                )
            """)
            
            # Insert realistic test data
            self._insert_test_data(cursor)
            conn.commit()
    
    def _insert_test_data(self, cursor):
        """Insert realistic test data."""
        # Insert trades data
        trades_data = [
            ('2024-01-01 09:30:00', 'BTC', 'buy', 45000.0, 0.1, 4.50),
            ('2024-01-01 10:15:00', 'ETH', 'buy', 2800.0, 2.0, 5.60),
            ('2024-01-01 11:00:00', 'BTC', 'sell', 46000.0, 0.05, 2.30),
            ('2024-01-01 14:30:00', 'ETH', 'sell', 2900.0, 1.0, 2.90),
            ('2024-01-02 09:00:00', 'BTC', 'buy', 47000.0, 0.2, 9.40),
        ]
        
        for trade in trades_data:
            cursor.execute("""
                INSERT INTO trades (timestamp, symbol, side, price, quantity, commission)
                VALUES (?, ?, ?, ?, ?, ?)
            """, trade)
        
        # Insert orders data
        orders_data = [
            ('order_001', 'filled', 'BTC', 'buy', 'market', 0.1, None, '2024-01-01 09:30:00', '2024-01-01 09:30:00', None),
            ('order_002', 'filled', 'ETH', 'buy', 'limit', 2.0, 2800.0, '2024-01-01 10:15:00', '2024-01-01 10:15:00', None),
            ('order_003', 'filled', 'BTC', 'sell', 'market', 0.05, None, '2024-01-01 11:00:00', '2024-01-01 11:00:00', None),
            ('order_004', 'filled', 'ETH', 'sell', 'limit', 1.0, 2900.0, '2024-01-01 14:30:00', '2024-01-01 14:30:00', None),
            ('order_005', 'filled', 'BTC', 'buy', 'market', 0.2, None, '2024-01-02 09:00:00', '2024-01-02 09:00:00', None),
        ]
        
        for order in orders_data:
            cursor.execute("""
                INSERT INTO orders (client_order_id, status, symbol, side, order_type, quantity, price, submit_timestamp, fill_timestamp, cancel_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, order)
        
        # Insert positions data
        positions_data = [
            ('BTC', 0.25, 46000.0, 47000.0, 250.0),
            ('ETH', 1.0, 2800.0, 2900.0, 100.0),
        ]
        
        for position in positions_data:
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, average_entry_price, current_price, unrealized_pnl)
                VALUES (?, ?, ?, ?, ?)
            """, position)
        
        # Insert equity curve data
        equity_data = [
            ('2024-01-01 09:00:00', 10000.0, 10000.0, 0.0, 0.0),
            ('2024-01-01 10:00:00', 10050.0, 9950.0, 50.0, 50.0),
            ('2024-01-01 11:00:00', 10100.0, 9900.0, 100.0, 50.0),
            ('2024-01-01 12:00:00', 10150.0, 9850.0, 150.0, 50.0),
            ('2024-01-02 09:00:00', 10200.0, 9800.0, 200.0, 50.0),
        ]
        
        for equity in equity_data:
            cursor.execute("""
                INSERT INTO equity_curve (timestamp, portfolio_value, cash_balance, total_pnl, daily_pnl)
                VALUES (?, ?, ?, ?, ?)
            """, equity)
    
    def _create_test_config(self):
        """Create test configuration."""
        import yaml
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
        
        with open(self.test_config_path, 'w') as f:
            yaml.dump(config_data, f)
    
    @pytest.mark.asyncio
    async def test_full_backup_restore_cycle(self):
        """Test complete backup and restore cycle."""
        # Create backup
        backup_metadata = await self.backup_manager.create_backup()
        
        # Verify backup was successful
        self.assertEqual(backup_metadata.status, 'success')
        self.assertEqual(len(backup_metadata.tables_backed_up), 4)
        self.assertGreater(backup_metadata.total_records, 0)
        
        # Create new database for restoration
        restore_db_path = Path(self.temp_dir) / "restore_test.db"
        
        # Restore backup
        restore_success = await self.backup_manager.restore_backup(
            backup_metadata.backup_id, str(restore_db_path)
        )
        self.assertTrue(restore_success)
        
        # Verify restored data matches original
        with sqlite3.connect(self.test_db_path) as original_conn:
            with sqlite3.connect(restore_db_path) as restored_conn:
                
                # Compare trades table
                original_trades = pd.read_sql_query("SELECT * FROM trades", original_conn)
                restored_trades = pd.read_sql_query("SELECT * FROM trades", restored_conn)
                
                self.assertEqual(len(original_trades), len(restored_trades))
                pd.testing.assert_frame_equal(original_trades, restored_trades)
                
                # Compare orders table
                original_orders = pd.read_sql_query("SELECT * FROM orders", original_conn)
                restored_orders = pd.read_sql_query("SELECT * FROM orders", restored_conn)
                
                self.assertEqual(len(original_orders), len(restored_orders))
                pd.testing.assert_frame_equal(original_orders, restored_orders)
                
                # Compare positions table
                original_positions = pd.read_sql_query("SELECT * FROM positions", original_conn)
                restored_positions = pd.read_sql_query("SELECT * FROM positions", restored_conn)
                
                self.assertEqual(len(original_positions), len(restored_positions))
                pd.testing.assert_frame_equal(original_positions, restored_positions)
                
                # Compare equity_curve table
                original_equity = pd.read_sql_query("SELECT * FROM equity_curve", original_conn)
                restored_equity = pd.read_sql_query("SELECT * FROM equity_curve", restored_conn)
                
                self.assertEqual(len(original_equity), len(restored_equity))
                pd.testing.assert_frame_equal(original_equity, restored_equity)
    
    @pytest.mark.asyncio
    async def test_backup_performance(self):
        """Test backup performance with large dataset."""
        # Create large dataset
        self._create_large_dataset()
        
        # Measure backup time
        start_time = time.time()
        backup_metadata = await self.backup_manager.create_backup("performance_test")
        backup_time = time.time() - start_time
        
        # Verify backup completed successfully
        self.assertEqual(backup_metadata.status, 'success')
        
        # Performance assertions (adjust based on system capabilities)
        self.assertLess(backup_time, 30.0)  # Should complete within 30 seconds
        self.assertGreater(backup_metadata.compression_ratio, 0.1)  # Should have some compression
        
        # Verify backup integrity
        backup_path = self.test_backup_dir / backup_metadata.backup_id
        integrity_result = await self.backup_manager._verify_backup_integrity(
            backup_path, backup_metadata
        )
        self.assertTrue(integrity_result)
    
    def _create_large_dataset(self):
        """Create large dataset for performance testing."""
        with sqlite3.connect(self.test_db_path) as conn:
            cursor = conn.cursor()
            
            # Insert large number of trades
            trades_data = []
            for i in range(1000):
                timestamp = datetime.now() - timedelta(days=i)
                trades_data.append((
                    timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'BTC' if i % 2 == 0 else 'ETH',
                    'buy' if i % 3 == 0 else 'sell',
                    45000.0 + (i % 1000),
                    0.1 + (i % 10) * 0.01,
                    4.50 + (i % 10) * 0.01
                ))
            
            cursor.executemany("""
                INSERT INTO trades (timestamp, symbol, side, price, quantity, commission)
                VALUES (?, ?, ?, ?, ?, ?)
            """, trades_data)
            
            # Insert large number of orders
            orders_data = []
            for i in range(1000):
                timestamp = datetime.now() - timedelta(days=i)
                orders_data.append((
                    f'order_{i:06d}',
                    'filled',
                    'BTC' if i % 2 == 0 else 'ETH',
                    'buy' if i % 3 == 0 else 'sell',
                    'market',
                    0.1 + (i % 10) * 0.01,
                    None,
                    timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    None
                ))
            
            cursor.executemany("""
                INSERT INTO orders (client_order_id, status, symbol, side, order_type, quantity, price, submit_timestamp, fill_timestamp, cancel_timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, orders_data)
            
            conn.commit()
    
    @pytest.mark.asyncio
    async def test_backup_failure_scenarios(self):
        """Test backup system under failure conditions."""
        # Test with non-existent database
        invalid_db_path = Path(self.temp_dir) / "nonexistent.db"
        invalid_backup_manager = BackupManager(
            str(self.test_config_path),
            str(invalid_db_path)
        )
        
        backup_metadata = await invalid_backup_manager.create_backup()
        self.assertEqual(backup_metadata.status, 'failed')
        self.assertIsNotNone(backup_metadata.error_message)
        
        # Test with corrupted backup file
        backup_metadata = await self.backup_manager.create_backup("corruption_test")
        backup_path = self.test_backup_dir / backup_metadata.backup_id
        
        # Corrupt a backup file
        trades_file = backup_path / "trades.parquet"
        if trades_file.exists():
            with open(trades_file, 'w') as f:
                f.write("corrupted data")
            
            # Verify integrity check fails
            integrity_result = await self.backup_manager._verify_backup_integrity(
                backup_path, backup_metadata
            )
            self.assertFalse(integrity_result)
    
    @pytest.mark.asyncio
    async def test_retention_policy_enforcement(self):
        """Test backup retention policy enforcement."""
        # Create multiple backups with different ages
        backup_ids = []
        
        for i in range(5):
            # Create backup with specific timestamp
            with patch('grodtd.storage.backup_manager.datetime') as mock_datetime:
                mock_time = datetime.now() - timedelta(days=i*2)  # 0, 2, 4, 6, 8 days old
                mock_datetime.now.return_value = mock_time
                mock_datetime.fromtimestamp.return_value = mock_time
                
                backup_metadata = await self.backup_manager.create_backup(f"backup_{i}")
                backup_ids.append(backup_metadata.backup_id)
        
        # Run cleanup
        await self.backup_manager.cleanup_old_backups()
        
        # Verify retention policy applied
        remaining_backups = self.backup_manager.list_backups()
        
        # Should keep recent backups (within retention_days=7)
        # and remove older ones
        self.assertLessEqual(len(remaining_backups), 4)  # At most 4 should remain
    
    @pytest.mark.asyncio
    async def test_concurrent_backup_operations(self):
        """Test concurrent backup operations."""
        # Create multiple concurrent backups
        tasks = []
        for i in range(3):
            task = asyncio.create_task(
                self.backup_manager.create_backup(f"concurrent_backup_{i}")
            )
            tasks.append(task)
        
        # Wait for all backups to complete
        backup_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all backups completed successfully
        for result in backup_results:
            if isinstance(result, Exception):
                self.fail(f"Backup failed with exception: {result}")
            else:
                self.assertEqual(result.status, 'success')
    
    @pytest.mark.asyncio
    async def test_backup_scheduler_integration(self):
        """Test backup scheduler integration."""
        scheduler = BackupScheduler(self.backup_manager)
        
        # Test scheduler start/stop
        await scheduler.start_scheduler()
        self.assertTrue(scheduler._running)
        
        await scheduler.stop_scheduler()
        self.assertFalse(scheduler._running)
    
    def test_backup_status_and_listing(self):
        """Test backup status and listing functionality."""
        # Get initial status
        status = self.backup_manager.get_backup_status()
        self.assertIn('backup_directory', status)
        self.assertIn('total_backups', status)
        self.assertIn('config', status)
        
        # List backups (should be empty initially)
        backups = self.backup_manager.list_backups()
        self.assertEqual(len(backups), 0)
    
    @pytest.mark.asyncio
    async def test_different_compression_algorithms(self):
        """Test different compression algorithms."""
        compression_algorithms = ['snappy', 'gzip', 'brotli']
        
        for compression in compression_algorithms:
            # Update config
            self.backup_manager.config.compression = compression
            
            # Create backup
            backup_metadata = await self.backup_manager.create_backup(f"compression_test_{compression}")
            
            # Verify backup success
            self.assertEqual(backup_metadata.status, 'success')
            
            # Verify backup files exist and are readable
            backup_path = self.test_backup_dir / backup_metadata.backup_id
            for table_name in backup_metadata.tables_backed_up:
                parquet_file = backup_path / f"{table_name}.parquet"
                self.assertTrue(parquet_file.exists())
                
                # Verify file can be read
                df = pd.read_parquet(parquet_file)
                self.assertGreater(len(df), 0)
    
    @pytest.mark.asyncio
    async def test_backup_with_empty_tables(self):
        """Test backup with empty tables."""
        # Create database with empty tables
        empty_db_path = Path(self.temp_dir) / "empty_test.db"
        with sqlite3.connect(empty_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE empty_table (id INTEGER)")
            conn.commit()
        
        # Create backup manager for empty database
        empty_backup_manager = BackupManager(
            str(self.test_config_path),
            str(empty_db_path)
        )
        
        # Create backup
        backup_metadata = await empty_backup_manager.create_backup("empty_test")
        
        # Verify backup completed (even with empty tables)
        self.assertEqual(backup_metadata.status, 'success')
        self.assertEqual(backup_metadata.total_records, 0)


if __name__ == '__main__':
    unittest.main()
