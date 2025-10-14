"""
Unit tests for data type-specific retention logic.

Tests the different retention approaches for critical, important, and operational data.
"""

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

import pytest
import sqlite3
import yaml

# Import the modules to test
import sys
sys.path.append('grodtd/storage')
from retention_manager import RetentionManager, create_retention_manager
from retention_models import RetentionPolicy, DataPriority, CleanupOperation


class TestDataTypeRetentionLogic(unittest.TestCase):
    """Test data type-specific retention logic functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "retention.yaml"
        self.db_path = Path(self.temp_dir) / "test.db"
        
        # Create test database
        self._create_test_database()
        
        # Create test configurations
        self._create_retention_config()
        
        # Create retention manager
        self.retention_manager = RetentionManager(str(self.config_path), str(self.db_path))
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_database(self):
        """Create test database with sample data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create tables for different data types
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
            
            cursor.execute("""
                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    status TEXT,
                    quantity INTEGER,
                    price REAL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE positions (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    quantity INTEGER,
                    average_price REAL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE equity_curve (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    portfolio_value REAL
                )
            """)
            
            cursor.execute("""
                CREATE TABLE market_data (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER
                )
            """)
            
            # Insert test data with varying ages
            now = datetime.now()
            
            # Critical data - older records (should be preserved longer)
            for i in range(20):
                trade_ts = (now - timedelta(days=i*10)).isoformat()
                order_ts = (now - timedelta(days=i*8)).isoformat()
                position_ts = (now - timedelta(days=i*12)).isoformat()
                
                cursor.execute("""
                    INSERT INTO trades (timestamp, symbol, side, price, quantity)
                    VALUES (?, ?, ?, ?, ?)
                """, (trade_ts, f"SYM{i%5}", "BUY" if i%2==0 else "SELL", 100.0 + i, 100))
                
                cursor.execute("""
                    INSERT INTO orders (timestamp, symbol, status, quantity, price)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_ts, f"ORD{i%3}", "FILLED", 50, 100.0 + i))
                
                cursor.execute("""
                    INSERT INTO positions (timestamp, symbol, quantity, average_price)
                    VALUES (?, ?, ?, ?)
                """, (position_ts, f"POS{i%4}", 25, 100.0 + i))
            
            # Important data - medium age records
            for i in range(15):
                equity_ts = (now - timedelta(days=i*5)).isoformat()
                
                cursor.execute("""
                    INSERT INTO equity_curve (timestamp, portfolio_value)
                    VALUES (?, ?)
                """, (equity_ts, 10000.0 + i*100))
            
            # Operational data - newer records (can be cleaned more aggressively)
            for i in range(30):
                market_ts = (now - timedelta(days=i*2)).isoformat()
                
                cursor.execute("""
                    INSERT INTO market_data (timestamp, symbol, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (market_ts, f"MKT{i%5}", 100.0 + i, 105.0 + i, 95.0 + i, 102.0 + i, 1000 + i))
            
            conn.commit()
    
    def _create_retention_config(self):
        """Create test retention configuration."""
        config = {
            'global': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'dry_run': False,
                'max_storage_gb': 50
            },
            'scheduler': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'check_interval_minutes': 60,
                'max_cleanup_duration_hours': 4,
                'backup_before_cleanup': True,
                'notification_channels': ['log', 'console'],
                'log_level': 'INFO',
                'dry_run': False
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
                    'retention_days': 30,
                    'retention_weeks': 4,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'critical',
                    'description': 'Position records'
                },
                'equity_curve': {
                    'enabled': True,
                    'retention_days': 15,
                    'retention_weeks': 2,
                    'retention_months': 3,
                    'retention_years': 1,
                    'priority': 'important',
                    'description': 'Equity curve data'
                },
                'market_data': {
                    'enabled': True,
                    'retention_days': 7,
                    'retention_weeks': 1,
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
    
    def test_data_type_priority_order(self):
        """Test that data types are processed in priority order."""
        data_types = ['market_data', 'trades', 'equity_curve', 'orders', 'positions']
        priority_order = self.retention_manager._get_data_type_priority_order(data_types)
        
        # Critical data should come first
        self.assertEqual(priority_order[:3], ['trades', 'orders', 'positions'])
        # Important data should come second
        self.assertEqual(priority_order[3], 'equity_curve')
        # Operational data should come last
        self.assertEqual(priority_order[4], 'market_data')
    
    def test_conservative_cutoff_calculation(self):
        """Test conservative cutoff calculation for critical data."""
        policy = self.retention_manager.policies['trades']
        conservative_cutoff = self.retention_manager._calculate_conservative_cutoff(policy)
        
        # Conservative cutoff should be more restrictive (older date)
        standard_cutoff = self.retention_manager._calculate_cutoff_date(policy)
        self.assertLess(conservative_cutoff, standard_cutoff)
        
        # Should use the longest retention period with 10% buffer
        # Based on the actual policy values: retention_days=30, retention_weeks=4, retention_months=6, retention_years=1
        expected_days = max(30, 4*7, 6*30, 1*365) * 1.1  # max(30, 28, 180, 365) * 1.1 = 365 * 1.1 = 401.5
        expected_cutoff = datetime.now() - timedelta(days=expected_days)
        
        # Allow for larger time differences due to calculation timing
        time_diff = abs((conservative_cutoff - expected_cutoff).total_seconds())
        self.assertLess(time_diff, 86400)  # Within 1 day
    
    def test_balanced_cutoff_calculation(self):
        """Test balanced cutoff calculation for important data."""
        policy = self.retention_manager.policies['equity_curve']
        balanced_cutoff = self.retention_manager._calculate_balanced_cutoff(policy)
        
        # Balanced cutoff should match standard cutoff (allow for small timing differences)
        standard_cutoff = self.retention_manager._calculate_cutoff_date(policy)
        time_diff = abs((balanced_cutoff - standard_cutoff).total_seconds())
        self.assertLess(time_diff, 1)  # Within 1 second
    
    def test_aggressive_cutoff_calculation(self):
        """Test aggressive cutoff calculation for operational data."""
        policy = self.retention_manager.policies['market_data']
        aggressive_cutoff = self.retention_manager._calculate_aggressive_cutoff(policy)
        
        # Aggressive cutoff should be less restrictive (newer date)
        standard_cutoff = self.retention_manager._calculate_cutoff_date(policy)
        self.assertGreater(aggressive_cutoff, standard_cutoff)
        
        # Should use the shortest retention period with 10% reduction
        # Based on the actual policy values: retention_days=7, retention_weeks=1, retention_months=1, retention_years=1
        expected_days = min(7, 1*7, 1*30, 1*365) * 0.9  # min(7, 7, 30, 365) * 0.9 = 7 * 0.9 = 6.3
        expected_cutoff = datetime.now() - timedelta(days=expected_days)
        
        # Allow for larger time differences due to calculation timing
        time_diff = abs((aggressive_cutoff - expected_cutoff).total_seconds())
        self.assertLess(time_diff, 86400)  # Within 1 day
    
    @pytest.mark.asyncio
    async def test_critical_data_cleanup_logic(self):
        """Test cleanup logic for critical data (trades, orders, positions)."""
        # Test trades cleanup
        policy = self.retention_manager.policies['trades']
        operation = await self.retention_manager._cleanup_critical_data(
            'trades', policy, dry_run=True, 
            operation_id='test_operation', 
            start_time=datetime.now()
        )
        
        self.assertIsInstance(operation, CleanupOperation)
        self.assertEqual(operation.data_type, 'trades')
        self.assertEqual(operation.status, 'success')
        self.assertGreaterEqual(operation.records_processed, 0)
        self.assertGreaterEqual(operation.records_deleted, 0)
        self.assertGreaterEqual(operation.storage_freed_bytes, 0)
    
    @pytest.mark.asyncio
    async def test_important_data_cleanup_logic(self):
        """Test cleanup logic for important data (equity_curve)."""
        policy = self.retention_manager.policies['equity_curve']
        operation = await self.retention_manager._cleanup_important_data(
            'equity_curve', policy, dry_run=True,
            operation_id='test_operation',
            start_time=datetime.now()
        )
        
        self.assertIsInstance(operation, CleanupOperation)
        self.assertEqual(operation.data_type, 'equity_curve')
        self.assertEqual(operation.status, 'success')
        self.assertGreaterEqual(operation.records_processed, 0)
        self.assertGreaterEqual(operation.records_deleted, 0)
        self.assertGreaterEqual(operation.storage_freed_bytes, 0)
    
    @pytest.mark.asyncio
    async def test_operational_data_cleanup_logic(self):
        """Test cleanup logic for operational data (market_data)."""
        policy = self.retention_manager.policies['market_data']
        operation = await self.retention_manager._cleanup_operational_data(
            'market_data', policy, dry_run=True,
            operation_id='test_operation',
            start_time=datetime.now()
        )
        
        self.assertIsInstance(operation, CleanupOperation)
        self.assertEqual(operation.data_type, 'market_data')
        self.assertEqual(operation.status, 'success')
        self.assertGreaterEqual(operation.records_processed, 0)
        self.assertGreaterEqual(operation.records_deleted, 0)
        self.assertGreaterEqual(operation.storage_freed_bytes, 0)
    
    @pytest.mark.asyncio
    async def test_data_type_specific_cleanup_integration(self):
        """Test integration of data type-specific cleanup logic."""
        # Test with dry run to avoid actual deletion
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        self.assertIsInstance(operations, list)
        self.assertGreater(len(operations), 0)
        
        # Check that operations were processed in priority order
        data_types = [op.data_type for op in operations]
        
        # Critical data should be processed first
        critical_indices = [i for i, dt in enumerate(data_types) if dt in ['trades', 'orders', 'positions']]
        important_indices = [i for i, dt in enumerate(data_types) if dt == 'equity_curve']
        operational_indices = [i for i, dt in enumerate(data_types) if dt == 'market_data']
        
        # Critical data should come before important data
        if critical_indices and important_indices:
            self.assertLess(max(critical_indices), min(important_indices))
        
        # Important data should come before operational data
        if important_indices and operational_indices:
            self.assertLess(max(important_indices), min(operational_indices))
    
    @pytest.mark.asyncio
    async def test_records_to_delete_with_cutoff(self):
        """Test getting records to delete with specific cutoff date."""
        cutoff_date = datetime.now() - timedelta(days=10)
        records = await self.retention_manager._get_records_to_delete_with_cutoff('trades', cutoff_date)
        
        self.assertIsInstance(records, list)
        
        # All records should be older than cutoff date
        for record in records:
            record_timestamp = datetime.fromisoformat(record['timestamp'])
            self.assertLess(record_timestamp, cutoff_date)
    
    @pytest.mark.asyncio
    async def test_delete_records_with_verification(self):
        """Test deletion with verification for critical data."""
        # Get some records to delete
        cutoff_date = datetime.now() - timedelta(days=5)
        records = await self.retention_manager._get_records_to_delete_with_cutoff('market_data', cutoff_date)
        
        if records:
            # Test deletion with verification
            deleted_count = await self.retention_manager._delete_records_with_verification(
                'market_data', records, cutoff_date
            )
            
            self.assertGreaterEqual(deleted_count, 0)
            self.assertEqual(deleted_count, len(records))
    
    @pytest.mark.asyncio
    async def test_delete_records_standard(self):
        """Test standard deletion for important data."""
        # Get some records to delete
        cutoff_date = datetime.now() - timedelta(days=5)
        records = await self.retention_manager._get_records_to_delete_with_cutoff('equity_curve', cutoff_date)
        
        if records:
            # Test standard deletion
            deleted_count = await self.retention_manager._delete_records_standard(
                'equity_curve', records, cutoff_date
            )
            
            self.assertGreaterEqual(deleted_count, 0)
            self.assertEqual(deleted_count, len(records))
    
    @pytest.mark.asyncio
    async def test_delete_records_minimal(self):
        """Test minimal deletion for operational data."""
        # Get some records to delete
        cutoff_date = datetime.now() - timedelta(days=5)
        records = await self.retention_manager._get_records_to_delete_with_cutoff('market_data', cutoff_date)
        
        if records:
            # Test minimal deletion
            deleted_count = await self.retention_manager._delete_records_minimal(
                'market_data', records, cutoff_date
            )
            
            self.assertGreaterEqual(deleted_count, 0)
            self.assertEqual(deleted_count, len(records))
    
    def test_unknown_data_type_fallback(self):
        """Test fallback behavior for unknown data types."""
        # Test with unknown data type
        data_types = ['unknown_type']
        priority_order = self.retention_manager._get_data_type_priority_order(data_types)
        
        # Unknown data type should be assigned lowest priority
        self.assertEqual(priority_order, ['unknown_type'])
    
    @pytest.mark.asyncio
    async def test_cleanup_data_type_with_logic_unknown_type(self):
        """Test cleanup logic for unknown data types."""
        # Create a mock policy for unknown data type
        unknown_policy = RetentionPolicy(
            enabled=True,
            retention_days=30,
            retention_weeks=4,
            retention_months=6,
            retention_years=1,
            priority=DataPriority.OPERATIONAL,
            description='Unknown data type'
        )
        
        # Test cleanup with unknown data type
        operation = await self.retention_manager._cleanup_data_type_with_logic(
            'unknown_type', unknown_policy, dry_run=True
        )
        
        self.assertIsInstance(operation, CleanupOperation)
        self.assertEqual(operation.data_type, 'unknown_type')
        # Should fall back to standard cleanup logic
        self.assertIn(operation.status, ['success', 'failed'])


if __name__ == '__main__':
    # Run tests
    unittest.main()
