"""
Integration tests for the Data Retention System.

Tests the complete retention workflow including cleanup operations,
storage monitoring, and data integrity preservation.
"""

import asyncio
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

# Import the modules to test
import sys
sys.path.append('grodtd/storage')
from retention_manager import RetentionManager, create_retention_manager
from retention_cli import main as cli_main


class TestRetentionSystemIntegration(unittest.TestCase):
    """Integration tests for the complete retention system."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "retention.yaml"
        self.db_path = Path(self.temp_dir) / "trading.db"
        self.logs_dir = Path(self.temp_dir) / "logs" / "retention"
        
        # Create logs directory
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Create comprehensive test database
        self._create_comprehensive_test_database()
        
        # Create realistic retention configuration
        self._create_retention_config()
        
        # Create retention manager
        self.retention_manager = RetentionManager(
            str(self.config_path), 
            str(self.db_path)
        )
    
    def tearDown(self):
        """Clean up integration test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_comprehensive_test_database(self):
        """Create comprehensive test database with realistic data."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create all tables with proper schema
            cursor.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    quantity INTEGER NOT NULL,
                    commission REAL DEFAULT 0.0
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
                    fill_timestamp TEXT,
                    cancel_timestamp TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE positions (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    average_entry_price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    unrealized_pnl REAL DEFAULT 0.0
                )
            """)
            
            cursor.execute("""
                CREATE TABLE equity_curve (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    portfolio_value REAL NOT NULL,
                    cash_balance REAL DEFAULT 0.0
                )
            """)
            
            cursor.execute("""
                CREATE TABLE market_data (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    volume INTEGER NOT NULL
                )
            """)
            
            # Insert realistic data with various ages
            base_time = datetime.now() - timedelta(days=500)
            
            # Insert trades with different ages
            for i in range(300):
                if i < 100:  # Very old trades (400+ days old)
                    timestamp = (base_time + timedelta(days=i)).isoformat()
                elif i < 200:  # Old trades (200-400 days old)
                    timestamp = (base_time + timedelta(days=200 + i)).isoformat()
                elif i < 250:  # Medium old trades (100-200 days old)
                    timestamp = (base_time + timedelta(days=300 + i)).isoformat()
                else:  # Recent trades (0-100 days old)
                    timestamp = (datetime.now() - timedelta(days=300-i)).isoformat()
                
                cursor.execute("""
                    INSERT INTO trades (timestamp, symbol, side, price, quantity, commission)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (timestamp, f"SYMBOL{i%10}", "BUY" if i%2==0 else "SELL", 
                      100.0 + i*0.1, 100, 1.0))
            
            # Insert orders with different ages
            for i in range(150):
                if i < 50:  # Very old orders
                    timestamp = (base_time + timedelta(days=i*2)).isoformat()
                elif i < 100:  # Old orders
                    timestamp = (base_time + timedelta(days=200 + i*2)).isoformat()
                else:  # Recent orders
                    timestamp = (datetime.now() - timedelta(days=150-i)).isoformat()
                
                cursor.execute("""
                    INSERT INTO orders (client_order_id, status, symbol, quantity, submit_timestamp, fill_timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (f"ORDER{i}", "FILLED", f"SYMBOL{i%10}", 100, timestamp, timestamp))
            
            # Insert current positions (recent data)
            for i in range(10):
                timestamp = datetime.now().isoformat()
                cursor.execute("""
                    INSERT INTO positions (symbol, quantity, average_entry_price, timestamp, unrealized_pnl)
                    VALUES (?, ?, ?, ?, ?)
                """, (f"SYMBOL{i}", 100, 100.0 + i, timestamp, i * 10.0))
            
            # Insert equity curve data (time series)
            for i in range(400):
                timestamp = (base_time + timedelta(days=i)).isoformat()
                cursor.execute("""
                    INSERT INTO equity_curve (timestamp, portfolio_value, cash_balance)
                    VALUES (?, ?, ?)
                """, (timestamp, 10000.0 + i * 10, 1000.0))
            
            # Insert market data (high frequency)
            for i in range(2000):
                timestamp = (base_time + timedelta(hours=i)).isoformat()
                cursor.execute("""
                    INSERT INTO market_data (timestamp, symbol, open_price, high_price, low_price, close_price, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, f"SYMBOL{i%10}", 100.0, 101.0, 99.0, 100.5, 1000))
    
    def _create_retention_config(self):
        """Create realistic retention configuration."""
        config = {
            'global': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'dry_run': False,
                'max_storage_gb': 10  # Small limit for testing
            },
            'retention_policies': {
                'trades': {
                    'enabled': True,
                    'retention_days': 90,      # Keep for 3 months
                    'retention_weeks': 12,    # Keep weekly for 3 months
                    'retention_months': 6,    # Keep monthly for 6 months
                    'retention_years': 2,     # Keep yearly for 2 years
                    'priority': 'critical',
                    'description': 'Trade records - critical for compliance'
                },
                'orders': {
                    'enabled': True,
                    'retention_days': 90,      # Keep for 3 months
                    'retention_weeks': 12,    # Keep weekly for 3 months
                    'retention_months': 6,    # Keep monthly for 6 months
                    'retention_years': 2,     # Keep yearly for 2 years
                    'priority': 'critical',
                    'description': 'Order records - critical for compliance'
                },
                'positions': {
                    'enabled': True,
                    'retention_days': 30,     # Keep for 1 month
                    'retention_weeks': 4,     # Keep weekly for 1 month
                    'retention_months': 3,    # Keep monthly for 3 months
                    'retention_years': 1,     # Keep yearly for 1 year
                    'priority': 'important',
                    'description': 'Position records - important for analysis'
                },
                'equity_curve': {
                    'enabled': True,
                    'retention_days': 180,    # Keep for 6 months
                    'retention_weeks': 26,    # Keep weekly for 6 months
                    'retention_months': 12,  # Keep monthly for 1 year
                    'retention_years': 3,    # Keep yearly for 3 years
                    'priority': 'important',
                    'description': 'Equity curve - important for performance tracking'
                },
                'market_data': {
                    'enabled': True,
                    'retention_days': 30,     # Keep for 1 month
                    'retention_weeks': 4,     # Keep weekly for 1 month
                    'retention_months': 3,    # Keep monthly for 3 months
                    'retention_years': 1,     # Keep yearly for 1 year
                    'priority': 'operational',
                    'description': 'Market data - operational for technical analysis'
                }
            },
            'cleanup': {
                'batch_size': 100,
                'max_cleanup_time_hours': 2,
                'backup_before_cleanup': True,
                'verify_integrity': True,
                'rollback_on_failure': True,
                'log_cleanup_operations': True,
                'create_audit_trail': True,
                'send_notifications': True
            },
            'storage_monitoring': {
                'enabled': True,
                'check_interval_hours': 1,
                'warning_threshold_percent': 70,
                'critical_threshold_percent': 90,
                'auto_cleanup_on_warning': False,
                'auto_cleanup_on_critical': True,
                'generate_reports': True,
                'report_frequency': 'daily',
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
                'enabled': True,
                'channels': ['log', 'console'],
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
    async def test_complete_retention_workflow(self):
        """Test complete retention workflow from start to finish."""
        # Get initial state
        initial_stats = await self.retention_manager.get_storage_stats()
        initial_trades = initial_stats.record_counts['trades']
        initial_orders = initial_stats.record_counts['orders']
        initial_positions = initial_stats.record_counts['positions']
        initial_equity = initial_stats.record_counts['equity_curve']
        initial_market = initial_stats.record_counts['market_data']
        
        print(f"Initial records: trades={initial_trades}, orders={initial_orders}, positions={initial_positions}, equity={initial_equity}, market={initial_market}")
        
        # Run dry run cleanup
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        # Verify operations were created
        self.assertEqual(len(operations), 5)  # All data types
        
        # Check that operations have reasonable numbers
        for operation in operations:
            self.assertGreater(operation.records_processed, 0)
            self.assertGreater(operation.storage_freed_bytes, 0)
            self.assertEqual(operation.status, 'success')
        
        # Verify specific data type operations
        trades_op = next(op for op in operations if op.data_type == 'trades')
        orders_op = next(op for op in operations if op.data_type == 'orders')
        positions_op = next(op for op in operations if op.data_type == 'positions')
        equity_op = next(op for op in operations if op.data_type == 'equity_curve')
        market_op = next(op for op in operations if op.data_type == 'market_data')
        
        # Trades and orders should have many records to delete (old data)
        self.assertGreater(trades_op.records_processed, 50)
        self.assertGreater(orders_op.records_processed, 25)
        
        # Positions should have few records to delete (recent data)
        self.assertLess(positions_op.records_processed, 10)
        
        # Equity curve should have moderate records to delete
        self.assertGreater(equity_op.records_processed, 100)
        
        # Market data should have many records to delete (high frequency, short retention)
        self.assertGreater(market_op.records_processed, 500)
        
        print(f"Cleanup simulation: trades={trades_op.records_processed}, orders={orders_op.records_processed}, positions={positions_op.records_processed}, equity={equity_op.records_processed}, market={market_op.records_processed}")
    
    @pytest.mark.asyncio
    async def test_storage_monitoring_integration(self):
        """Test storage monitoring integration."""
        # Get storage stats
        stats = await self.retention_manager.get_storage_stats()
        
        # Verify stats structure
        self.assertIsInstance(stats.total_size_bytes, int)
        self.assertGreater(stats.total_size_bytes, 0)
        
        # Verify data type breakdown
        self.assertIn('trades', stats.data_type_breakdown)
        self.assertIn('orders', stats.data_type_breakdown)
        self.assertIn('positions', stats.data_type_breakdown)
        self.assertIn('equity_curve', stats.data_type_breakdown)
        self.assertIn('market_data', stats.data_type_breakdown)
        
        # Verify record counts
        self.assertEqual(stats.record_counts['trades'], 300)
        self.assertEqual(stats.record_counts['orders'], 150)
        self.assertEqual(stats.record_counts['positions'], 10)
        self.assertEqual(stats.record_counts['equity_curve'], 400)
        self.assertEqual(stats.record_counts['market_data'], 2000)
        
        # Verify date ranges
        self.assertIsNotNone(stats.oldest_record_date)
        self.assertIsNotNone(stats.newest_record_date)
        self.assertLess(stats.oldest_record_date, stats.newest_record_date)
    
    @pytest.mark.asyncio
    async def test_retention_policies_integration(self):
        """Test retention policies integration."""
        policies = self.retention_manager.policies
        
        # Verify all policies are loaded
        self.assertEqual(len(policies), 5)
        
        # Verify policy priorities
        self.assertEqual(policies['trades'].priority.value, 'critical')
        self.assertEqual(policies['orders'].priority.value, 'critical')
        self.assertEqual(policies['positions'].priority.value, 'important')
        self.assertEqual(policies['equity_curve'].priority.value, 'important')
        self.assertEqual(policies['market_data'].priority.value, 'operational')
        
        # Verify retention periods
        self.assertEqual(policies['trades'].retention_days, 90)
        self.assertEqual(policies['orders'].retention_days, 90)
        self.assertEqual(policies['positions'].retention_days, 30)
        self.assertEqual(policies['equity_curve'].retention_days, 180)
        self.assertEqual(policies['market_data'].retention_days, 30)
    
    @pytest.mark.asyncio
    async def test_cleanup_audit_trail(self):
        """Test cleanup audit trail creation."""
        # Run cleanup to generate audit trail
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        # Check that audit trail was created
        audit_file = self.logs_dir / "cleanup_audit.json"
        if audit_file.exists():
            with open(audit_file, 'r') as f:
                audit_data = json.load(f)
            
            self.assertIn('cleanup_timestamp', audit_data)
            self.assertIn('operations', audit_data)
            self.assertIn('total_records_deleted', audit_data)
            self.assertIn('total_storage_freed_bytes', audit_data)
            
            # Verify operation details in audit
            self.assertEqual(len(audit_data['operations']), 5)
            for op_data in audit_data['operations']:
                self.assertIn('operation_id', op_data)
                self.assertIn('data_type', op_data)
                self.assertIn('records_processed', op_data)
                self.assertIn('records_deleted', op_data)
                self.assertIn('storage_freed_bytes', op_data)
                self.assertIn('status', op_data)
    
    @pytest.mark.asyncio
    async def test_data_integrity_verification(self):
        """Test data integrity verification."""
        # Run cleanup with integrity verification
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        # Verify all operations succeeded
        for operation in operations:
            self.assertEqual(operation.status, 'success')
            self.assertIsNone(operation.error_message)
    
    @pytest.mark.asyncio
    async def test_cleanup_notifications(self):
        """Test cleanup notifications."""
        # Mock notification channels
        with patch('builtins.print') as mock_print:
            operations = await self.retention_manager.run_cleanup(dry_run=True)
            
            # Verify notifications were sent
            self.assertTrue(mock_print.called)
    
    @pytest.mark.asyncio
    async def test_retention_status_integration(self):
        """Test retention status integration."""
        status = self.retention_manager.get_retention_status()
        
        # Verify status structure
        self.assertIn('enabled', status)
        self.assertIn('policies_count', status)
        self.assertIn('active_policies', status)
        self.assertIn('storage_stats', status)
        self.assertIn('config', status)
        
        # Verify values
        self.assertTrue(status['enabled'])
        self.assertEqual(status['policies_count'], 5)
        self.assertEqual(status['active_policies'], 5)
        
        # Verify storage stats
        storage_stats = status['storage_stats']
        self.assertIn('total_size_mb', storage_stats)
        self.assertIn('data_type_breakdown', storage_stats)
        self.assertIn('record_counts', storage_stats)
        
        # Verify config
        config = status['config']
        self.assertIn('dry_run', config)
        self.assertIn('max_storage_gb', config)
        self.assertIn('cleanup_schedule', config)
    
    @pytest.mark.asyncio
    async def test_cleanup_with_specific_data_types(self):
        """Test cleanup with specific data types."""
        # Test cleanup for only trades and orders
        operations = await self.retention_manager.run_cleanup(
            data_types=['trades', 'orders'],
            dry_run=True
        )
        
        # Verify only specified data types were processed
        self.assertEqual(len(operations), 2)
        data_types = [op.data_type for op in operations]
        self.assertIn('trades', data_types)
        self.assertIn('orders', data_types)
        self.assertNotIn('positions', data_types)
        self.assertNotIn('equity_curve', data_types)
        self.assertNotIn('market_data', data_types)
    
    @pytest.mark.asyncio
    async def test_cleanup_with_disabled_policy(self):
        """Test cleanup with disabled policy."""
        # Disable trades policy
        self.retention_manager.policies['trades'].enabled = False
        
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        # Verify trades were not processed
        data_types = [op.data_type for op in operations]
        self.assertNotIn('trades', data_types)
        self.assertIn('orders', data_types)
        self.assertIn('positions', data_types)
        self.assertIn('equity_curve', data_types)
        self.assertIn('market_data', data_types)
    
    def test_retention_manager_factory(self):
        """Test retention manager factory function."""
        manager = create_retention_manager(str(self.config_path), str(self.db_path))
        
        self.assertIsInstance(manager, RetentionManager)
        self.assertEqual(manager.config_path, self.config_path)
        self.assertEqual(manager.db_path, self.db_path)
    
    @pytest.mark.asyncio
    async def test_cleanup_performance(self):
        """Test cleanup performance with large dataset."""
        start_time = datetime.now()
        
        operations = await self.retention_manager.run_cleanup(dry_run=True)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Verify performance is reasonable (should complete within 30 seconds)
        self.assertLess(duration, 30)
        
        # Verify all operations completed successfully
        for operation in operations:
            self.assertEqual(operation.status, 'success')
    
    @pytest.mark.asyncio
    async def test_storage_threshold_monitoring(self):
        """Test storage threshold monitoring."""
        # Get storage stats
        stats = await self.retention_manager.get_storage_stats()
        
        # Calculate storage usage percentage
        max_storage_bytes = self.retention_manager.config['global']['max_storage_gb'] * 1024 * 1024 * 1024
        usage_percent = (stats.total_size_bytes / max_storage_bytes) * 100
        
        # Verify storage monitoring would trigger appropriate actions
        if usage_percent > self.retention_manager.config['storage_monitoring']['critical_threshold_percent']:
            # Should trigger auto-cleanup
            self.assertTrue(self.retention_manager.config['storage_monitoring']['auto_cleanup_on_critical'])
        elif usage_percent > self.retention_manager.config['storage_monitoring']['warning_threshold_percent']:
            # Should trigger warning
            self.assertFalse(self.retention_manager.config['storage_monitoring']['auto_cleanup_on_warning'])


if __name__ == '__main__':
    # Run integration tests
    unittest.main()
