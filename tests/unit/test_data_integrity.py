"""
Unit tests for data integrity preservation functionality.

Tests data integrity verification, archival processes, and recovery procedures.
"""

import asyncio
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Import the modules to test
import sys
sys.path.append('grodtd/storage')
from retention_integrity import DataIntegrityManager


class TestDataIntegrityManager(unittest.TestCase):
    """Test data integrity preservation functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.backup_dir = Path(self.temp_dir) / "backups"
        self.logs_dir = Path(self.temp_dir) / "logs"
        
        # Create test database
        self._create_test_database()
        
        # Create integrity manager
        self.integrity_manager = DataIntegrityManager(
            str(self.db_path), 
            str(self.backup_dir), 
            str(self.logs_dir)
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_database(self):
        """Create test database with sample data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create test tables
            cursor.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price REAL NOT NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    trade_id INTEGER,
                    FOREIGN KEY (trade_id) REFERENCES trades(id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE market_data (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume REAL NOT NULL
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX idx_trades_timestamp ON trades(timestamp)")
            cursor.execute("CREATE INDEX idx_orders_timestamp ON orders(timestamp)")
            cursor.execute("CREATE INDEX idx_market_data_timestamp ON market_data(timestamp)")
            
            # Insert sample data
            base_time = datetime.now() - timedelta(days=30)
            
            for i in range(50):
                timestamp = (base_time + timedelta(hours=i)).isoformat()
                
                # Insert trade
                cursor.execute(
                    "INSERT INTO trades (timestamp, symbol, quantity, price) VALUES (?, ?, ?, ?)",
                    (timestamp, "AAPL", 100.0, 150.0 + i)
                )
                trade_id = cursor.lastrowid
                
                # Insert order
                cursor.execute(
                    "INSERT INTO orders (timestamp, symbol, side, quantity, trade_id) VALUES (?, ?, ?, ?, ?)",
                    (timestamp, "AAPL", "BUY", 100.0, trade_id)
                )
                
                # Insert market data
                cursor.execute(
                    "INSERT INTO market_data (timestamp, symbol, price, volume) VALUES (?, ?, ?, ?)",
                    (timestamp, "AAPL", 150.0 + i, 1000.0)
                )
            
            conn.commit()
    
    @pytest.mark.asyncio
    async def test_verify_database_integrity(self):
        """Test database integrity verification."""
        result = await self.integrity_manager.verify_database_integrity()
        
        self.assertIsNotNone(result)
        self.assertIn('timestamp', result)
        self.assertIn('status', result)
        self.assertIn('checks', result)
        self.assertIn('overall_health', result)
        
        # Check individual verification results
        checks = result['checks']
        self.assertIn('connectivity', checks)
        self.assertIn('schema', checks)
        self.assertIn('consistency', checks)
        self.assertIn('foreign_keys', checks)
        self.assertIn('indexes', checks)
        self.assertIn('checksum', checks)
        
        # All checks should pass for a healthy database
        for check_name, check_result in checks.items():
            self.assertEqual(check_result['status'], 'passed', f"Check {check_name} failed: {check_result}")
    
    @pytest.mark.asyncio
    async def test_check_database_connectivity(self):
        """Test database connectivity check."""
        result = await self.integrity_manager._check_database_connectivity()
        
        self.assertEqual(result['status'], 'passed')
        self.assertIn('message', result)
        self.assertIn('database_count', result)
        self.assertIn('test_query_result', result)
        self.assertEqual(result['test_query_result'], 1)
    
    @pytest.mark.asyncio
    async def test_check_schema_integrity(self):
        """Test schema integrity check."""
        result = await self.integrity_manager._check_schema_integrity()
        
        self.assertEqual(result['status'], 'passed')
        self.assertIn('message', result)
        self.assertIn('table_count', result)
        self.assertIn('tables', result)
        self.assertEqual(result['table_count'], 3)  # trades, orders, market_data
        
        # Check table structures
        tables = result['tables']
        self.assertIn('trades', tables)
        self.assertIn('orders', tables)
        self.assertIn('market_data', tables)
    
    @pytest.mark.asyncio
    async def test_check_data_consistency(self):
        """Test data consistency check."""
        result = await self.integrity_manager._check_data_consistency()
        
        self.assertEqual(result['status'], 'passed')
        self.assertIn('message', result)
        self.assertIn('table_checks', result)
        
        # Check table consistency
        table_checks = result['table_checks']
        self.assertIn('trades', table_checks)
        self.assertIn('orders', table_checks)
        self.assertIn('market_data', table_checks)
        
        for table, check in table_checks.items():
            self.assertEqual(check['status'], 'passed')
            self.assertIn('record_count', check)
            self.assertIn('null_checks', check)
    
    @pytest.mark.asyncio
    async def test_check_foreign_key_integrity(self):
        """Test foreign key integrity check."""
        result = await self.integrity_manager._check_foreign_key_integrity()
        
        self.assertEqual(result['status'], 'passed')
        self.assertIn('message', result)
        self.assertIn('foreign_key_checks', result)
    
    @pytest.mark.asyncio
    async def test_check_index_integrity(self):
        """Test index integrity check."""
        result = await self.integrity_manager._check_index_integrity()
        
        self.assertEqual(result['status'], 'passed')
        self.assertIn('message', result)
        self.assertIn('index_checks', result)
        
        # Should have indexes for timestamp columns
        index_checks = result['index_checks']
        self.assertGreater(len(index_checks), 0)
    
    @pytest.mark.asyncio
    async def test_calculate_database_checksum(self):
        """Test database checksum calculation."""
        result = await self.integrity_manager._calculate_database_checksum()
        
        self.assertEqual(result['status'], 'passed')
        self.assertIn('message', result)
        self.assertIn('file_checksum', result)
        self.assertIn('content_checksum', result)
        self.assertIn('table_count', result)
        
        # Verify checksum file was created
        self.assertTrue(self.integrity_manager.checksum_file.exists())
        
        # Load and verify checksum data
        with open(self.integrity_manager.checksum_file, 'r') as f:
            checksum_data = json.load(f)
        
        self.assertIn('timestamp', checksum_data)
        self.assertIn('file_checksum', checksum_data)
        self.assertIn('content_checksum', checksum_data)
        self.assertIn('table_checksums', checksum_data)
    
    @pytest.mark.asyncio
    async def test_create_integrity_backup(self):
        """Test creating integrity backup."""
        result = await self.integrity_manager.create_integrity_backup("test_backup")
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('message', result)
        self.assertIn('backup_metadata', result)
        
        # Check backup file exists
        backup_path = self.backup_dir / "test_backup.db"
        self.assertTrue(backup_path.exists())
        
        # Check metadata file exists
        metadata_path = self.backup_dir / "test_backup_metadata.json"
        self.assertTrue(metadata_path.exists())
        
        # Verify backup metadata
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        self.assertIn('backup_name', metadata)
        self.assertIn('created_at', metadata)
        self.assertIn('backup_size_bytes', metadata)
        self.assertIn('integrity_verified', metadata)
        self.assertEqual(metadata['backup_name'], 'test_backup')
        self.assertTrue(metadata['integrity_verified'])
    
    @pytest.mark.asyncio
    async def test_verify_backup_integrity(self):
        """Test backup integrity verification."""
        # Create a backup first
        backup_result = await self.integrity_manager.create_integrity_backup("test_backup")
        self.assertEqual(backup_result['status'], 'success')
        
        backup_path = self.backup_dir / "test_backup.db"
        result = await self.integrity_manager._verify_backup_integrity(backup_path)
        
        self.assertEqual(result['status'], 'passed')
        self.assertIn('message', result)
    
    @pytest.mark.asyncio
    async def test_restore_from_backup(self):
        """Test restoring from backup."""
        # Create a backup first
        backup_result = await self.integrity_manager.create_integrity_backup("test_restore_backup")
        self.assertEqual(backup_result['status'], 'success')
        
        # Modify the original database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO trades (timestamp, symbol, quantity, price) VALUES (?, ?, ?, ?)",
                          ("2024-01-01T00:00:00", "TEST", 1.0, 1.0))
            conn.commit()
        
        # Restore from backup
        result = await self.integrity_manager.restore_from_backup("test_restore_backup")
        
        self.assertEqual(result['status'], 'success')
        self.assertIn('message', result)
        self.assertIn('backup_name', result)
        
        # Verify the test record was removed (restored from backup)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades WHERE symbol = 'TEST'")
            count = cursor.fetchone()[0]
            self.assertEqual(count, 0)  # Should be 0 after restore
    
    @pytest.mark.asyncio
    async def test_get_integrity_status(self):
        """Test getting integrity status."""
        # Create a backup and run integrity check first
        await self.integrity_manager.create_integrity_backup("status_test_backup")
        await self.integrity_manager.verify_database_integrity()
        
        result = await self.integrity_manager.get_integrity_status()
        
        self.assertIsNotNone(result)
        self.assertIn('timestamp', result)
        self.assertIn('database_path', result)
        self.assertIn('latest_verification', result)
        self.assertIn('available_backups', result)
        self.assertIn('backup_metadata', result)
        self.assertIn('integrity_log_file', result)
        self.assertIn('checksum_file', result)
        
        # Should have at least one backup
        self.assertGreater(result['available_backups'], 0)
        
        # Should have latest verification
        self.assertIsNotNone(result['latest_verification'])
    
    def test_log_integrity_verification(self):
        """Test logging integrity verification."""
        verification_result = {
            "timestamp": datetime.now().isoformat(),
            "status": "passed",
            "checks": {"test": {"status": "passed"}}
        }
        
        # This is a synchronous method, so we can test it directly
        self.integrity_manager._log_integrity_verification(verification_result)
        
        # Check that log file was created and contains the result
        self.assertTrue(self.integrity_manager.integrity_log_file.exists())
        
        with open(self.integrity_manager.integrity_log_file, 'r') as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 0)
            
            # Check the last line contains our verification result
            last_entry = json.loads(lines[-1])
            self.assertEqual(last_entry['status'], 'passed')


if __name__ == '__main__':
    unittest.main()
