"""
Unit tests for the Retention Scheduler.

Tests automated scheduling, integration with retention manager,
and scheduler status monitoring.
"""

import asyncio
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

import pytest
import yaml

# Import the modules to test
import sys
sys.path.append('grodtd/storage')
from retention_scheduler import (
    RetentionScheduler, SchedulerConfig, SchedulerStatus, 
    create_retention_scheduler
)


class TestSchedulerConfig(unittest.TestCase):
    """Test scheduler configuration functionality."""
    
    def test_scheduler_config_creation(self):
        """Test creating scheduler configuration."""
        config = SchedulerConfig(
            enabled=True,
            cleanup_schedule='03:00',
            check_interval_minutes=60,
            max_cleanup_duration_hours=4,
            backup_before_cleanup=True,
            notification_channels=['log', 'console'],
            log_level='INFO',
            dry_run=False
        )
        
        self.assertTrue(config.enabled)
        self.assertEqual(config.cleanup_schedule, '03:00')
        self.assertEqual(config.check_interval_minutes, 60)
        self.assertTrue(config.backup_before_cleanup)
        self.assertIn('log', config.notification_channels)
        self.assertIn('console', config.notification_channels)


class TestRetentionScheduler(unittest.TestCase):
    """Test retention scheduler functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "retention.yaml"
        self.db_path = Path(self.temp_dir) / "test.db"
        self.backup_config_path = Path(self.temp_dir) / "backup.yaml"
        
        # Create test database
        self._create_test_database()
        
        # Create test configurations
        self._create_retention_config()
        self._create_backup_config()
        
        # Create scheduler
        self.scheduler = RetentionScheduler(
            str(self.config_path), 
            str(self.db_path),
            str(self.backup_config_path)
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def _create_test_database(self):
        """Create test database."""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
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
            
            # Insert test data
            base_time = datetime.now() - timedelta(days=100)
            for i in range(50):
                timestamp = (base_time + timedelta(days=i)).isoformat()
                cursor.execute("""
                    INSERT INTO trades (timestamp, symbol, side, price, quantity)
                    VALUES (?, ?, ?, ?, ?)
                """, (timestamp, f"SYMBOL{i%5}", "BUY" if i%2==0 else "SELL", 100.0 + i, 100))
    
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
    
    def _create_backup_config(self):
        """Create test backup configuration."""
        config = {
            'backup_directory': str(Path(self.temp_dir) / 'backups'),
            'retention_days': 7,
            'retention_weeks': 4,
            'retention_months': 12,
            'retention_years': 3,
            'compression': 'snappy',
            'backup_time': '02:00',
            'enabled': True,
            'tables_to_backup': ['trades'],
            'verify_integrity': True,
            'max_backup_size_mb': 1000
        }
        
        with open(self.backup_config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
    
    def test_scheduler_initialization(self):
        """Test scheduler initialization."""
        self.assertIsNotNone(self.scheduler)
        self.assertIsNotNone(self.scheduler.config)
        self.assertIsNotNone(self.scheduler.retention_manager)
        self.assertIsNotNone(self.scheduler.backup_manager)
        self.assertFalse(self.scheduler._running)
    
    def test_config_loading(self):
        """Test configuration loading."""
        config = self.scheduler.config
        
        self.assertTrue(config.enabled)
        self.assertEqual(config.cleanup_schedule, '03:00')
        self.assertEqual(config.check_interval_minutes, 60)
        self.assertTrue(config.backup_before_cleanup)
        self.assertIn('log', config.notification_channels)
        self.assertIn('console', config.notification_channels)
        self.assertFalse(config.dry_run)
    
    def test_should_run_cleanup(self):
        """Test cleanup scheduling logic."""
        # Test with current time matching cleanup schedule
        with patch('retention_scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 3, 0, 0)
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Should run if no previous cleanup today
            self.scheduler._last_cleanup = None
            self.assertTrue(self.scheduler._should_run_cleanup())
            
            # Should not run if already cleaned up today
            self.scheduler._last_cleanup = datetime(2024, 1, 1, 2, 0, 0)
            self.assertFalse(self.scheduler._should_run_cleanup())
            
            # Should run if last cleanup was yesterday
            self.scheduler._last_cleanup = datetime(2023, 12, 31, 3, 0, 0)
            self.assertTrue(self.scheduler._should_run_cleanup())
    
    def test_should_run_cleanup_time_tolerance(self):
        """Test cleanup scheduling with time tolerance."""
        with patch('retention_scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 3, 30, 0)  # 30 minutes after cleanup time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Should still run within tolerance (60 minutes check interval)
            self.scheduler._last_cleanup = None
            self.assertTrue(self.scheduler._should_run_cleanup())
    
    def test_should_run_cleanup_outside_time(self):
        """Test cleanup scheduling outside cleanup time."""
        with patch('retention_scheduler.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, 10, 0, 0)  # 10 AM
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            
            # Should not run outside cleanup time
            self.scheduler._last_cleanup = None
            self.assertFalse(self.scheduler._should_run_cleanup())
    
    def test_get_status(self):
        """Test getting scheduler status."""
        status = self.scheduler.get_status()
        
        self.assertIsInstance(status, SchedulerStatus)
        self.assertFalse(status.running)
        self.assertIsNone(status.last_cleanup)
        self.assertEqual(status.total_cleanups, 0)
        self.assertEqual(status.successful_cleanups, 0)
        self.assertEqual(status.failed_cleanups, 0)
        self.assertIsNone(status.last_error)
        self.assertEqual(status.uptime_seconds, 0.0)
    
    def test_get_status_with_running_scheduler(self):
        """Test getting status from running scheduler."""
        # Simulate running scheduler
        self.scheduler._running = True
        self.scheduler._start_time = datetime.now() - timedelta(seconds=100)
        self.scheduler._last_cleanup = datetime.now() - timedelta(hours=1)
        self.scheduler._total_cleanups = 5
        self.scheduler._successful_cleanups = 4
        self.scheduler._failed_cleanups = 1
        self.scheduler._last_error = "Test error"
        
        status = self.scheduler.get_status()
        
        self.assertTrue(status.running)
        self.assertIsNotNone(status.last_cleanup)
        self.assertEqual(status.total_cleanups, 5)
        self.assertEqual(status.successful_cleanups, 4)
        self.assertEqual(status.failed_cleanups, 1)
        self.assertEqual(status.last_error, "Test error")
        self.assertGreater(status.uptime_seconds, 0)
    
    @pytest.mark.asyncio
    async def test_manual_cleanup(self):
        """Test manual cleanup operation."""
        result = await self.scheduler.run_manual_cleanup(['trades'])
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('operations_count', result)
        self.assertIn('successful_operations', result)
        self.assertIn('failed_operations', result)
        self.assertIn('total_records_deleted', result)
        self.assertIn('total_storage_freed_bytes', result)
        self.assertIn('operations', result)
    
    @pytest.mark.asyncio
    async def test_manual_cleanup_all_data_types(self):
        """Test manual cleanup for all data types."""
        result = await self.scheduler.run_manual_cleanup()
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertGreaterEqual(result['operations_count'], 0)
    
    def test_get_retention_status(self):
        """Test getting retention system status."""
        status = self.scheduler.get_retention_status()
        
        self.assertIsInstance(status, dict)
        self.assertIn('enabled', status)
        self.assertIn('policies_count', status)
        self.assertIn('active_policies', status)
        self.assertIn('storage_stats', status)
        self.assertIn('config', status)
    
    def test_get_storage_stats(self):
        """Test getting storage statistics."""
        stats = self.scheduler.get_storage_stats()
        
        self.assertIsInstance(stats, dict)
        self.assertIn('total_size_bytes', stats)
        self.assertIn('total_size_mb', stats)
        self.assertIn('data_type_breakdown', stats)
        self.assertIn('record_counts', stats)
    
    @pytest.mark.asyncio
    async def test_scheduler_start_stop(self):
        """Test scheduler start and stop."""
        # Start scheduler
        await self.scheduler.start()
        self.assertTrue(self.scheduler._running)
        self.assertIsNotNone(self.scheduler._task)
        
        # Stop scheduler
        await self.scheduler.stop()
        self.assertFalse(self.scheduler._running)
        self.assertIsNone(self.scheduler._task)
    
    @pytest.mark.asyncio
    async def test_scheduler_start_when_disabled(self):
        """Test scheduler start when disabled."""
        # Disable scheduler
        self.scheduler.config.enabled = False
        
        await self.scheduler.start()
        self.assertFalse(self.scheduler._running)
        self.assertIsNone(self.scheduler._task)
    
    @pytest.mark.asyncio
    async def test_scheduler_start_when_already_running(self):
        """Test scheduler start when already running."""
        # Start scheduler
        await self.scheduler.start()
        self.assertTrue(self.scheduler._running)
        
        # Try to start again
        await self.scheduler.start()
        self.assertTrue(self.scheduler._running)  # Should still be running
    
    @pytest.mark.asyncio
    async def test_scheduler_stop_when_not_running(self):
        """Test scheduler stop when not running."""
        # Stop scheduler when not running
        await self.scheduler.stop()
        self.assertFalse(self.scheduler._running)
    
    @pytest.mark.asyncio
    async def test_run_cleanup_cycle_with_backup(self):
        """Test running cleanup cycle with backup."""
        # Mock backup manager
        with patch.object(self.scheduler.backup_manager, 'create_backup') as mock_backup:
            mock_backup.return_value = Mock(
                status='success',
                backup_id='test_backup',
                error_message=None
            )
            
            # Mock retention manager
            with patch.object(self.scheduler.retention_manager, 'run_cleanup') as mock_cleanup:
                mock_cleanup.return_value = [
                    Mock(
                        data_type='trades',
                        records_deleted=10,
                        storage_freed_bytes=1024,
                        status='success',
                        duration_seconds=1.0,
                        error_message=None
                    )
                ]
                
                # Run cleanup cycle
                await self.scheduler._run_cleanup_cycle()
                
                # Verify backup was created
                mock_backup.assert_called_once()
                
                # Verify cleanup was run
                mock_cleanup.assert_called_once()
                
                # Verify statistics were updated
                self.assertEqual(self.scheduler._total_cleanups, 1)
                self.assertEqual(self.scheduler._successful_cleanups, 1)
                self.assertEqual(self.scheduler._failed_cleanups, 0)
                self.assertIsNotNone(self.scheduler._last_cleanup)
    
    @pytest.mark.asyncio
    async def test_run_cleanup_cycle_without_backup(self):
        """Test running cleanup cycle without backup."""
        # Disable backup before cleanup
        self.scheduler.config.backup_before_cleanup = False
        
        # Mock retention manager
        with patch.object(self.scheduler.retention_manager, 'run_cleanup') as mock_cleanup:
            mock_cleanup.return_value = [
                Mock(
                    data_type='trades',
                    records_deleted=10,
                    storage_freed_bytes=1024,
                    status='success',
                    duration_seconds=1.0,
                    error_message=None
                )
            ]
            
            # Run cleanup cycle
            await self.scheduler._run_cleanup_cycle()
            
            # Verify cleanup was run
            mock_cleanup.assert_called_once()
            
            # Verify statistics were updated
            self.assertEqual(self.scheduler._total_cleanups, 1)
            self.assertEqual(self.scheduler._successful_cleanups, 1)
            self.assertEqual(self.scheduler._failed_cleanups, 0)
    
    @pytest.mark.asyncio
    async def test_run_cleanup_cycle_with_failure(self):
        """Test running cleanup cycle with failure."""
        # Mock retention manager to raise exception
        with patch.object(self.scheduler.retention_manager, 'run_cleanup') as mock_cleanup:
            mock_cleanup.side_effect = Exception("Cleanup failed")
            
            # Run cleanup cycle
            await self.scheduler._run_cleanup_cycle()
            
            # Verify statistics were updated
            self.assertEqual(self.scheduler._total_cleanups, 0)
            self.assertEqual(self.scheduler._successful_cleanups, 0)
            self.assertEqual(self.scheduler._failed_cleanups, 1)
            self.assertIsNotNone(self.scheduler._last_error)
    
    def test_factory_function(self):
        """Test factory function for creating scheduler."""
        scheduler = create_retention_scheduler(
            str(self.config_path),
            str(self.db_path),
            str(self.backup_config_path)
        )
        
        self.assertIsInstance(scheduler, RetentionScheduler)
        self.assertEqual(scheduler.config_path, self.config_path)
        self.assertEqual(scheduler.db_path, self.db_path)
        self.assertEqual(scheduler.backup_config_path, self.backup_config_path)


if __name__ == '__main__':
    # Run tests
    unittest.main()
