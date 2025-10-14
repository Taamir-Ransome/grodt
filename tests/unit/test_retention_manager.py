"""
Unit tests for the Retention Manager.

Tests data retention policies, cleanup operations, and storage monitoring.
"""

import asyncio
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import yaml

# Import the modules to test
import sys
sys.path.append('grodtd/storage')
from retention_manager import RetentionManager, create_retention_manager
from retention_models import RetentionPolicy, CleanupOperation, StorageStats, DataPriority


class TestRetentionPolicy(unittest.TestCase):
    """Test retention policy functionality."""
    
    def test_retention_policy_creation(self):
        """Test creating retention policy."""
        policy = RetentionPolicy(
            data_type="trades",
            enabled=True,
            retention_days=365,
            retention_weeks=52,
            retention_months=24,
            retention_years=7,
            priority=DataPriority.CRITICAL,
            description="Trade records"
        )
        
        self.assertEqual(policy.data_type, "trades")
        self.assertTrue(policy.enabled)
        self.assertEqual(policy.retention_days, 365)
        self.assertEqual(policy.priority, DataPriority.CRITICAL)


class TestRetentionManager(unittest.TestCase):
    """Test retention manager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "retention.yaml"
        self.db_path = Path(self.temp_dir) / "test.db"
        
        # Create test database
        self._create_test_database()
        
        # Create test configuration
        self._create_test_config()
        
        # Create retention manager
        self.retention_manager = RetentionManager(
            str(self.config_path), 
            str(self.db_path)
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_database(self):
        """Create test database with sample data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    side TEXT,
                    price REAL,
                    quantity INTEGER
                )
            """)
            
            # Create orders table
            cursor.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    client_order_id TEXT,
                    status TEXT,
                    symbol TEXT,
                    quantity INTEGER,
                    submit_timestamp TEXT,
                    fill_timestamp TEXT
                )
            """)
            
            # Create positions table
            cursor.execute("""
                CREATE TABLE positions (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    quantity INTEGER,
                    average_entry_price REAL,
                    timestamp TEXT
                )
            """)
            
            # Create equity_curve table
            cursor.execute("""
                CREATE TABLE equity_curve (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    portfolio_value REAL
                )
            """)
            
            # Create market_data table
            cursor.execute("""
                CREATE TABLE market_data (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    open_price REAL,
                    high_price REAL,
                    low_price REAL,
                    close_price REAL,
                    volume INTEGER
                )
            """)
            
            # Insert test data
            base_time = datetime.now() - timedelta(days=400)
            
            # Insert trades (some old, some recent)
            for i in range(100):
                timestamp = (base_time + timedelta(days=i)).isoformat()
                cursor.execute("""
                    INSERT INTO trades (timestamp, symbol, side, price, quantity)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, f"SYMBOL{i%10}", "BUY" if i%2==0 else "SELL", 100.0 + i, 100))
            
            # Insert orders (some old, some recent)
            for i in range(50):
                timestamp = (base_time + timedelta(days=i*2)).isoformat()
                cursor.execute("""
                    INSERT INTO orders (client_order_id, status, symbol, quantity, submit_timestamp, fill_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"ORDER{i}", "FILLED", f"SYMBOL{i%10}", 100, timestamp, timestamp))
            
            # Insert positions (current data)
            for i in range(10):
                timestamp = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO positions (symbol, quantity, average_entry_price, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (f"SYMBOL{i}", 100, 100.0 + i, timestamp))
            
            # Insert equity_curve (time series)
            for i in range(200):
                timestamp = (base_time + timedelta(days=i)).isoformat()
                cursor.execute("""
                    INSERT INTO equity_curve (timestamp, portfolio_value)
                    VALUES (?, ?)
                """, (timestamp, 10000.0 + i * 10))
            
            # Insert market_data (high frequency)
            for i in range(1000):
                timestamp = (base_time + timedelta(hours=i)).isoformat()
                cursor.execute("""
                    INSERT INTO market_data (timestamp, symbol, open_price, high_price, low_price, close_price, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, f"SYMBOL{i%10}", 100.0, 101.0, 99.0, 100.5, 1000))
    
    def _create_test_config(self):
        """Create test configuration."""
        config = {
            'global': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'dry_run': False,
                'max_storage_gb': 50
            },
            'retention_policies': {
                'trades': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Trade records'
                },
                'orders': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Order records'
                },
                'positions': {
                    'enabled': True,
                    'retention_days': 7,
                    'retention_weeks': 2,
                    'retention_months': 3,
                    'retention_years': 1,
                    'priority': 'important',
                    'description': 'Position records'
                },
                'equity_curve': {
                    'enabled': True,
                    'retention_days': 60,
                    'retention_weeks': 8,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'important',
                    'description': 'Equity curve data'
                },
                'market_data': {
                    'enabled': True,
                    'retention_days': 7,
                    'retention_weeks': 2,
                    'retention_months': 1,
                    'retention_years': 1,
                    'priority': 'operational',
                    'description': 'Market data'
                }
            },
            'cleanup': {
                'batch_size': 100,
                'max_cleanup_time_hours': 1,
                'backup_before_cleanup': False,
                'verify_integrity': True,
                'rollback_on_failure': True,
                'log_cleanup_operations': True,
                'create_audit_trail': True,
                'send_notifications': False
            },
            'storage_monitoring': {
                'enabled': True,
                'check_interval_hours': 6,
                'warning_threshold_percent': 80,
                'critical_threshold_percent': 95,
                'auto_cleanup_on_warning': False,
                'auto_cleanup_on_critical': True,
                'generate_reports': True,
                'report_frequency': 'weekly',
                'include_trends': True
            },
            'data_integrity': {
                'verify_before_cleanup': True,
                'checksum_verification': True,
                'backup_verification': True,
                'enable_recovery': True,
                'recovery_window_days': 7,
                'test_recovery_procedures': True
            },
            'notifications': {
                'enabled': False,
                'channels': ['log'],
                'on_cleanup_start': True,
                'on_cleanup_complete': True,
                'on_cleanup_failure': True,
                'on_storage_warning': True,
                'on_storage_critical': True,
                'include_statistics': True,
                'include_storage_info': True,
                'include_error_details': True
            },
            'compliance': {
                'audit_enabled': True,
                'audit_retention_days': 2555,
                'log_data_access': True,
                'log_cleanup_decisions': True,
                'generate_compliance_reports': True,
                'report_frequency': 'monthly',
                'include_data_lineage': True
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
    
    def test_retention_manager_initialization(self):
        """Test retention manager initialization."""
        self.assertIsNotNone(self.retention_manager)
        self.assertTrue(self.retention_manager.config_manager.is_enabled())
        self.assertEqual(len(self.retention_manager.policies), 5)
    
    def test_retention_policies_loading(self):
        """Test retention policies are loaded correctly."""
        policies = self.retention_manager.policies
        
        # Check trades policy
        self.assertIn('trades', policies)
        trades_policy = policies['trades']
        self.assertTrue(trades_policy.enabled)
        self.assertEqual(trades_policy.priority, DataPriority.CRITICAL)
        self.assertEqual(trades_policy.retention_days, 30)
        
        # Check market_data policy
        self.assertIn('market_data', policies)
        market_policy = policies['market_data']
        self.assertTrue(market_policy.enabled)
        self.assertEqual(market_policy.priority, DataPriority.OPERATIONAL)
        self.assertEqual(market_policy.retention_days, 7)
    
    @pytest.mark.asyncio
    async def test_get_storage_stats(self):
        """Test getting storage statistics."""
        stats = await self.retention_manager.get_storage_stats()
        
        self.assertIsInstance(stats, StorageStats)
        self.assertGreater(stats.total_size_bytes, 0)
        self.assertIn('trades', stats.record_counts)
        self.assertIn('orders', stats.record_counts)
        self.assertIn('positions', stats.record_counts)
        self.assertIn('equity_curve', stats.record_counts)
        self.assertIn('market_data', stats.record_counts)
        
        # Check record counts
        self.assertEqual(stats.record_counts['trades'], 100)
        self.assertEqual(stats.record_counts['orders'], 50)
        self.assertEqual(stats.record_counts['positions'], 10)
        self.assertEqual(stats.record_counts['equity_curve'], 200)
        self.assertEqual(stats.record_counts['market_data'], 1000)
    
    @pytest.mark.asyncio
    async def test_cleanup_dry_run(self):
        """Test cleanup operation in dry run mode."""
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        self.assertIsInstance(operations, list)
        self.assertGreater(len(operations), 0)
        
        # Check that operations were created for enabled policies
        data_types = [op.data_type for op in operations]
        self.assertIn('trades', data_types)
        self.assertIn('orders', data_types)
        self.assertIn('positions', data_types)
        self.assertIn('equity_curve', data_types)
        self.assertIn('market_data', data_types)
        
        # Check operation details
        for operation in operations:
            self.assertIsInstance(operation, CleanupOperation)
            self.assertGreater(operation.records_processed, 0)
            self.assertEqual(operation.records_deleted, operation.records_processed)  # Dry run
            self.assertGreater(operation.storage_freed_bytes, 0)
            self.assertEqual(operation.status, 'success')
    
    @pytest.mark.asyncio
    async def test_cleanup_specific_data_type(self):
        """Test cleanup for specific data type."""
        operations = await self.retention_manager.run_cleanup(
            data_types=['trades'], 
            dry_run=True
        )
        
        self.assertEqual(len(operations), 1)
        operation = operations[0]
        self.assertEqual(operation.data_type, 'trades')
        self.assertGreater(operation.records_processed, 0)
    
    @pytest.mark.asyncio
    async def test_cleanup_disabled_policy(self):
        """Test cleanup with disabled policy."""
        # Disable trades policy
        self.retention_manager.policies['trades'].enabled = False
        
        operations = await self.retention_manager.run_cleanup(
            data_types=['trades'], 
            dry_run=True
        )
        
        # Should not create operations for disabled policy
        self.assertEqual(len(operations), 0)
    
    def test_calculate_cutoff_date(self):
        """Test cutoff date calculation."""
        policy = self.retention_manager.policies['trades']
        cutoff_date = self.retention_manager._calculate_cutoff_date(policy)
        
        # Should be 28 days ago (retention_weeks * 7 = 4 * 7 = 28) - the most restrictive period
        expected_date = datetime.now() - timedelta(days=28)
        self.assertAlmostEqual(
            cutoff_date.timestamp(), 
            expected_date.timestamp(), 
            delta=60  # 1 minute tolerance
        )
    
    @pytest.mark.asyncio
    async def test_get_records_to_delete(self):
        """Test getting records to delete."""
        policy = self.retention_manager.policies['trades']
        records = await self.retention_manager._get_records_to_delete('trades', policy)
        
        self.assertIsInstance(records, list)
        self.assertGreater(len(records), 0)
        
        # Check record structure
        if records:
            record = records[0]
            self.assertIn('id', record)
            self.assertIn('timestamp', record)
            self.assertIn('symbol', record)
            self.assertIn('side', record)
            self.assertIn('price', record)
            self.assertIn('quantity', record)
    
    @pytest.mark.asyncio
    async def test_calculate_storage_freed(self):
        """Test storage freed calculation."""
        policy = self.retention_manager.policies['trades']
        records = await self.retention_manager._get_records_to_delete('trades', policy)
        
        if records:
            storage_freed = await self.retention_manager._calculate_storage_freed('trades', records)
            self.assertGreater(storage_freed, 0)
    
    def test_retention_status(self):
        """Test getting retention status."""
        status = self.retention_manager.get_retention_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('enabled', status)
        self.assertIn('policies_count', status)
        self.assertIn('active_policies', status)
        self.assertIn('storage_stats', status)
        self.assertIn('config', status)
        
        self.assertTrue(status['enabled'])
        self.assertEqual(status['policies_count'], 5)
        self.assertEqual(status['active_policies'], 5)
    
    @pytest.mark.asyncio
    async def test_cleanup_operation_logging(self):
        """Test cleanup operation logging."""
        # Mock logger to capture log messages
        with patch.object(self.retention_manager.logger, 'info') as mock_info:
            operations = await self.retention_manager.run_cleanup(dry_run=True)
            
            # Check that logging occurred
            self.assertTrue(mock_info.called)
    
    def test_data_priority_enum(self):
        """Test data priority enum values."""
        self.assertEqual(DataPriority.CRITICAL.value, 'critical')
        self.assertEqual(DataPriority.IMPORTANT.value, 'important')
        self.assertEqual(DataPriority.OPERATIONAL.value, 'operational')
    
    @pytest.mark.asyncio
    async def test_cleanup_with_no_records(self):
        """Test cleanup when no records need deletion."""
        # Create a policy with very long retention
        policy = RetentionPolicy(
            data_type="test_table",
            enabled=True,
            retention_days=3650,  # 10 years
            retention_weeks=520,
            retention_months=120,
            retention_years=10,
            priority=DataPriority.CRITICAL,
            description="Test policy"
        )
        
        # Mock the database to return no records
        with patch.object(self.retention_manager, '_get_records_to_delete', return_value=[]):
            operation = await self.retention_manager._cleanup_data_type('test_table', policy, dry_run=True)
            
            self.assertEqual(operation.records_processed, 0)
            self.assertEqual(operation.records_deleted, 0)
            self.assertEqual(operation.storage_freed_bytes, 0)
            self.assertEqual(operation.status, 'success')


class TestRetentionManagerIntegration(unittest.TestCase):
    """Integration tests for retention manager."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "retention.yaml"
        self.db_path = Path(self.temp_dir) / "test.db"
        
        # Create test database with more realistic data
        self._create_realistic_test_database()
        self._create_test_config()
        
        self.retention_manager = RetentionManager(
            str(self.config_path), 
            str(self.db_path)
        )
    
    def tearDown(self):
        """Clean up integration test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_realistic_test_database(self):
        """Create realistic test database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create tables with proper schema
            cursor.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    client_order_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    submit_timestamp TEXT NOT NULL,
                    fill_timestamp TEXT
                )
            """)
            
            # Insert realistic data with proper timestamps
            base_time = datetime.now() - timedelta(days=400)
            
            # Insert trades with various ages
            for i in range(200):
                # Mix of old and recent trades
                if i < 50:  # Very old trades (should be deleted)
                    timestamp = (base_time + timedelta(days=i)).isoformat()
                elif i < 100:  # Medium old trades
                    timestamp = (base_time + timedelta(days=200 + i)).isoformat()
                else:  # Recent trades
                    timestamp = (datetime.now() - timedelta(days=i-100)).isoformat()
                
                cursor.execute("""
                    INSERT INTO trades (timestamp, symbol, side, price, quantity)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, f"SYMBOL{i%5}", "BUY" if i%2==0 else "SELL", 100.0 + i*0.1, 100))
            
            # Insert orders
            for i in range(100):
                timestamp = (base_time + timedelta(days=i*2)).isoformat()
                cursor.execute("""
                    INSERT INTO orders (client_order_id, status, symbol, quantity, submit_timestamp, fill_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"ORDER{i}", "FILLED", f"SYMBOL{i%5}", 100, timestamp, timestamp))
    
    def _create_test_config(self):
        """Create test configuration."""
        config = {
            'global': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'dry_run': False,
                'max_storage_gb': 50
            },
            'retention_policies': {
                'trades': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Trade records'
                },
                'orders': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Order records'
                }
            },
            'cleanup': {
                'batch_size': 50,
                'max_cleanup_time_hours': 1,
                'backup_before_cleanup': False,
                'verify_integrity': True,
                'rollback_on_failure': True,
                'log_cleanup_operations': True,
                'create_audit_trail': True,
                'send_notifications': False
            },
            'storage_monitoring': {
                'enabled': True,
                'check_interval_hours': 6,
                'warning_threshold_percent': 80,
                'critical_threshold_percent': 95,
                'auto_cleanup_on_warning': False,
                'auto_cleanup_on_critical': True,
                'generate_reports': True,
                'report_frequency': 'weekly',
                'include_trends': True
            },
            'data_integrity': {
                'verify_before_cleanup': True,
                'checksum_verification': True,
                'backup_verification': True,
                'enable_recovery': True,
                'recovery_window_days': 7,
                'test_recovery_procedures': True
            },
            'notifications': {
                'enabled': False,
                'channels': ['log'],
                'on_cleanup_start': True,
                'on_cleanup_complete': True,
                'on_cleanup_failure': True,
                'on_storage_warning': True,
                'on_storage_critical': True,
                'include_statistics': True,
                'include_storage_info': True,
                'include_error_details': True
            },
            'compliance': {
                'audit_enabled': True,
                'audit_retention_days': 2555,
                'log_data_access': True,
                'log_cleanup_decisions': True,
                'generate_compliance_reports': True,
                'report_frequency': 'monthly',
                'include_data_lineage': True
            }
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
    
    @pytest.mark.asyncio
    async def test_full_cleanup_workflow(self):
        """Test complete cleanup workflow."""
        # Get initial record counts
        initial_stats = await self.retention_manager.get_storage_stats()
        initial_trades = initial_stats.record_counts['trades']
        initial_orders = initial_stats.record_counts['orders']
        
        # Run cleanup
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        # Verify operations
        self.assertEqual(len(operations), 2)  # trades and orders
        
        trades_operation = next(op for op in operations if op.data_type == 'trades')
        orders_operation = next(op for op in operations if op.data_type == 'orders')
        
        # Verify operation details
        self.assertGreater(trades_operation.records_processed, 0)
        self.assertGreater(orders_operation.records_processed, 0)
        
        # Verify that old records would be deleted
        self.assertGreater(trades_operation.records_processed, 0)
        self.assertGreater(orders_operation.records_processed, 0)
    
    @pytest.mark.asyncio
    async def test_storage_monitoring(self):
        """Test storage monitoring functionality."""
        stats = await self.retention_manager.get_storage_stats()
        
        self.assertIsInstance(stats, StorageStats)
        self.assertGreater(stats.total_size_bytes, 0)
        self.assertIn('trades', stats.record_counts)
        self.assertIn('orders', stats.record_counts)
        
        # Verify data type breakdown
        self.assertIn('trades', stats.data_type_breakdown)
        self.assertIn('orders', stats.data_type_breakdown)
    
    def test_factory_function(self):
        """Test factory function for creating retention manager."""
        manager = create_retention_manager(str(self.config_path), str(self.db_path))
        
        self.assertIsInstance(manager, RetentionManager)
        self.assertEqual(manager.config_path, self.config_path)
        self.assertEqual(manager.db_path, self.db_path)


if __name__ == '__main__':
    # Run tests
    unittest.main()
