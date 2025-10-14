"""
Retention Scheduler for GRODT Trading System.

This module handles automated scheduling of data retention and cleanup operations,
integrating with the existing backup system and retention manager.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
from dataclasses import dataclass
import json

from retention_manager import RetentionManager, create_retention_manager
from backup_manager import BackupManager, create_backup_manager


@dataclass
class SchedulerConfig:
    """Configuration for the retention scheduler."""
    enabled: bool
    cleanup_schedule: str  # 'HH:MM' format
    check_interval_minutes: int
    max_cleanup_duration_hours: int
    backup_before_cleanup: bool
    notification_channels: List[str]
    log_level: str
    dry_run: bool


@dataclass
class SchedulerStatus:
    """Status information for the scheduler."""
    running: bool
    last_cleanup: Optional[datetime]
    next_cleanup: Optional[datetime]
    total_cleanups: int
    successful_cleanups: int
    failed_cleanups: int
    last_error: Optional[str]
    uptime_seconds: float


class RetentionScheduler:
    """
    Automated scheduler for data retention and cleanup operations.
    
    Features:
    - Configurable scheduling (daily, weekly, etc.)
    - Integration with backup system
    - Monitoring and alerting
    - Graceful shutdown handling
    - Performance metrics
    """
    
    def __init__(self, config_path: str, db_path: str, backup_config_path: str):
        self.config_path = Path(config_path)
        self.db_path = Path(db_path)
        self.backup_config_path = Path(backup_config_path)
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize components
        self.retention_manager = create_retention_manager(config_path, db_path)
        self.backup_manager = create_backup_manager(backup_config_path, db_path)
        
        # Scheduler state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._start_time: Optional[datetime] = None
        self._last_cleanup: Optional[datetime] = None
        self._total_cleanups = 0
        self._successful_cleanups = 0
        self._failed_cleanups = 0
        self._last_error: Optional[str] = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
    
    def _load_config(self) -> SchedulerConfig:
        """Load scheduler configuration."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
            else:
                config_data = self._get_default_config()
                self._save_config(config_data)
            
            # Extract scheduler-specific config
            scheduler_config = config_data.get('scheduler', {})
            
            return SchedulerConfig(
                enabled=scheduler_config.get('enabled', True),
                cleanup_schedule=scheduler_config.get('cleanup_schedule', '03:00'),
                check_interval_minutes=scheduler_config.get('check_interval_minutes', 60),
                max_cleanup_duration_hours=scheduler_config.get('max_cleanup_duration_hours', 4),
                backup_before_cleanup=scheduler_config.get('backup_before_cleanup', True),
                notification_channels=scheduler_config.get('notification_channels', ['log']),
                log_level=scheduler_config.get('log_level', 'INFO'),
                dry_run=scheduler_config.get('dry_run', False)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load scheduler config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> SchedulerConfig:
        """Get default scheduler configuration."""
        return SchedulerConfig(
            enabled=True,
            cleanup_schedule='03:00',
            check_interval_minutes=60,
            max_cleanup_duration_hours=4,
            backup_before_cleanup=True,
            notification_channels=['log'],
            log_level='INFO',
            dry_run=False
        )
    
    def _save_config(self, config_data: Dict[str, Any]):
        """Save configuration to YAML file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save scheduler config: {e}")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self):
        """Start the retention scheduler."""
        if self._running:
            self.logger.warning("Retention scheduler is already running")
            return
        
        if not self.config.enabled:
            self.logger.info("Retention scheduler is disabled")
            return
        
        self.logger.info("Starting retention scheduler...")
        
        self._running = True
        self._start_time = datetime.now()
        self._task = asyncio.create_task(self._scheduler_loop())
        
        self.logger.info(f"Retention scheduler started (schedule: {self.config.cleanup_schedule}, dry_run: {self.config.dry_run})")
    
    async def stop(self):
        """Stop the retention scheduler."""
        if not self._running:
            return
        
        self.logger.info("Stopping retention scheduler...")
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Retention scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Check if it's time for cleanup
                if self._should_run_cleanup():
                    await self._run_cleanup_cycle()
                
                # Wait until next check
                await asyncio.sleep(self.config.check_interval_minutes * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}")
                self._last_error = str(e)
                await asyncio.sleep(300)  # Wait 5 minutes before retry
    
    def _should_run_cleanup(self) -> bool:
        """Check if cleanup should run based on schedule."""
        current_time = datetime.now()
        cleanup_hour, cleanup_minute = map(int, self.config.cleanup_schedule.split(':'))
        
        # Check if current time matches cleanup time (within check interval tolerance)
        time_diff = abs((current_time.hour * 60 + current_time.minute) - 
                       (cleanup_hour * 60 + cleanup_minute))
        
        # Run cleanup if we're within the check interval of the scheduled time
        if time_diff <= self.config.check_interval_minutes:
            # Only run if we haven't run today yet
            if self._last_cleanup is None or self._last_cleanup.date() < current_time.date():
                return True
        
        return False
    
    async def _run_cleanup_cycle(self):
        """Run a complete cleanup cycle."""
        cycle_start = datetime.now()
        self.logger.info("Starting retention cleanup cycle")
        
        try:
            # Create backup before cleanup if configured
            if self.config.backup_before_cleanup and not self.config.dry_run:
                await self._create_cleanup_backup()
            
            # Run retention cleanup
            operations = await self.retention_manager.run_cleanup(dry_run=self.config.dry_run)
            
            # Process results
            successful_ops = [op for op in operations if op.status == 'success']
            failed_ops = [op for op in operations if op.status == 'failed']
            
            # Update statistics
            self._total_cleanups += 1
            if failed_ops:
                self._failed_cleanups += 1
                self._last_error = f"{len(failed_ops)} operations failed"
            else:
                self._successful_cleanups += 1
                self._last_error = None
            
            self._last_cleanup = cycle_start
            
            # Log results
            total_deleted = sum(op.records_deleted for op in operations)
            total_freed = sum(op.storage_freed_bytes for op in operations)
            duration = (datetime.now() - cycle_start).total_seconds()
            
            self.logger.info(f"Cleanup cycle completed: {len(operations)} operations, "
                           f"{total_deleted} records, {total_freed / 1024 / 1024:.2f} MB freed, "
                           f"{duration:.2f}s duration")
            
            # Send notifications
            await self._send_cleanup_notifications(operations, duration)
            
        except Exception as e:
            self.logger.error(f"Cleanup cycle failed: {e}")
            self._failed_cleanups += 1
            self._last_error = str(e)
            
            # Send error notification
            await self._send_error_notification(str(e))
    
    async def _create_cleanup_backup(self):
        """Create backup before cleanup operation."""
        try:
            self.logger.info("Creating backup before cleanup...")
            backup_metadata = await self.backup_manager.create_backup()
            
            if backup_metadata.status == 'success':
                self.logger.info(f"Backup created successfully: {backup_metadata.backup_id}")
            else:
                self.logger.warning(f"Backup creation failed: {backup_metadata.error_message}")
                
        except Exception as e:
            self.logger.error(f"Failed to create cleanup backup: {e}")
            raise
    
    async def _send_cleanup_notifications(self, operations: List, duration: float):
        """Send notifications about cleanup completion."""
        if not self.config.notification_channels:
            return
        
        try:
            total_deleted = sum(op.records_deleted for op in operations)
            total_freed = sum(op.storage_freed_bytes for op in operations)
            successful_ops = len([op for op in operations if op.status == 'success'])
            failed_ops = len([op for op in operations if op.status == 'failed'])
            
            message = (f"Retention cleanup completed: {successful_ops} successful, {failed_ops} failed, "
                      f"{total_deleted} records deleted, {total_freed / 1024 / 1024:.2f} MB freed, "
                      f"{duration:.2f}s duration")
            
            for channel in self.config.notification_channels:
                if channel == 'log':
                    self.logger.info(f"NOTIFICATION: {message}")
                elif channel == 'console':
                    print(f"NOTIFICATION: {message}")
                elif channel == 'file':
                    await self._write_notification_to_file(message)
                    
        except Exception as e:
            self.logger.error(f"Failed to send cleanup notifications: {e}")
    
    async def _send_error_notification(self, error_message: str):
        """Send error notification."""
        try:
            message = f"Retention cleanup failed: {error_message}"
            
            for channel in self.config.notification_channels:
                if channel == 'log':
                    self.logger.error(f"NOTIFICATION: {message}")
                elif channel == 'console':
                    print(f"NOTIFICATION: {message}")
                elif channel == 'file':
                    await self._write_notification_to_file(message)
                    
        except Exception as e:
            self.logger.error(f"Failed to send error notification: {e}")
    
    async def _write_notification_to_file(self, message: str):
        """Write notification to file."""
        try:
            notification_file = Path('logs/retention/notifications.log')
            notification_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(notification_file, 'a') as f:
                f.write(f"{datetime.now().isoformat()} - {message}\n")
                
        except Exception as e:
            self.logger.error(f"Failed to write notification to file: {e}")
    
    def get_status(self) -> SchedulerStatus:
        """Get current scheduler status."""
        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()
        
        # Calculate next cleanup time
        next_cleanup = None
        if self._running:
            current_time = datetime.now()
            cleanup_hour, cleanup_minute = map(int, self.config.cleanup_schedule.split(':'))
            
            # Calculate next cleanup time
            next_cleanup_time = current_time.replace(
                hour=cleanup_hour, 
                minute=cleanup_minute, 
                second=0, 
                microsecond=0
            )
            
            # If the time has passed today, schedule for tomorrow
            if next_cleanup_time <= current_time:
                next_cleanup_time += timedelta(days=1)
            
            next_cleanup = next_cleanup_time
        
        return SchedulerStatus(
            running=self._running,
            last_cleanup=self._last_cleanup,
            next_cleanup=next_cleanup,
            total_cleanups=self._total_cleanups,
            successful_cleanups=self._successful_cleanups,
            failed_cleanups=self._failed_cleanups,
            last_error=self._last_error,
            uptime_seconds=uptime
        )
    
    async def run_manual_cleanup(self, data_types: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run manual cleanup operation."""
        self.logger.info(f"Running manual cleanup for data types: {data_types or 'all'}")
        
        try:
            operations = await self.retention_manager.run_cleanup(
                data_types=data_types,
                dry_run=self.config.dry_run
            )
            
            # Process results
            successful_ops = [op for op in operations if op.status == 'success']
            failed_ops = [op for op in operations if op.status == 'failed']
            
            total_deleted = sum(op.records_deleted for op in operations)
            total_freed = sum(op.storage_freed_bytes for op in operations)
            
            result = {
                'success': len(failed_ops) == 0,
                'operations_count': len(operations),
                'successful_operations': len(successful_ops),
                'failed_operations': len(failed_ops),
                'total_records_deleted': total_deleted,
                'total_storage_freed_bytes': total_freed,
                'operations': [
                    {
                        'data_type': op.data_type,
                        'records_deleted': op.records_deleted,
                        'storage_freed_bytes': op.storage_freed_bytes,
                        'status': op.status,
                        'duration_seconds': op.duration_seconds,
                        'error_message': op.error_message
                    }
                    for op in operations
                ]
            }
            
            self.logger.info(f"Manual cleanup completed: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Manual cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations_count': 0,
                'successful_operations': 0,
                'failed_operations': 0,
                'total_records_deleted': 0,
                'total_storage_freed_bytes': 0,
                'operations': []
            }
    
    def get_retention_status(self) -> Dict[str, Any]:
        """Get retention system status."""
        return self.retention_manager.get_retention_status()
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            stats = asyncio.run(self.retention_manager.get_storage_stats())
            return {
                'total_size_bytes': stats.total_size_bytes,
                'total_size_mb': stats.total_size_bytes / (1024 * 1024),
                'data_type_breakdown': stats.data_type_breakdown,
                'record_counts': stats.record_counts,
                'oldest_record_date': stats.oldest_record_date.isoformat() if stats.oldest_record_date else None,
                'newest_record_date': stats.newest_record_date.isoformat() if stats.newest_record_date else None,
                'last_cleanup_date': stats.last_cleanup_date.isoformat() if stats.last_cleanup_date else None
            }
        except Exception as e:
            return {'error': str(e)}


# Factory function for creating retention scheduler
def create_retention_scheduler(
    config_path: str, 
    db_path: str, 
    backup_config_path: str
) -> RetentionScheduler:
    """Create a new retention scheduler instance."""
    return RetentionScheduler(config_path, db_path, backup_config_path)


# CLI interface for the scheduler
async def main():
    """Main entry point for the retention scheduler."""
    import argparse
    
    parser = argparse.ArgumentParser(description="GRODT Retention Scheduler")
    parser.add_argument('--config', default='configs/retention.yaml',
                       help='Path to retention configuration file')
    parser.add_argument('--db', default='data/trading.db',
                       help='Path to SQLite database file')
    parser.add_argument('--backup-config', default='configs/backup.yaml',
                       help='Path to backup configuration file')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon (continuous operation)')
    parser.add_argument('--manual-cleanup', action='store_true',
                       help='Run manual cleanup and exit')
    parser.add_argument('--data-types', nargs='+',
                       help='Specific data types for manual cleanup')
    parser.add_argument('--status', action='store_true',
                       help='Show scheduler status and exit')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/retention/scheduler.log')
        ]
    )
    
    # Create logs directory
    Path('logs/retention').mkdir(parents=True, exist_ok=True)
    
    # Create scheduler
    scheduler = create_retention_scheduler(args.config, args.db, args.backup_config)
    
    try:
        if args.status:
            # Show status and exit
            status = scheduler.get_status()
            print(f"Scheduler Status: {'Running' if status.running else 'Stopped'}")
            print(f"Last cleanup: {status.last_cleanup or 'Never'}")
            print(f"Next cleanup: {status.next_cleanup or 'Not scheduled'}")
            print(f"Total cleanups: {status.total_cleanups}")
            print(f"Successful: {status.successful_cleanups}")
            print(f"Failed: {status.failed_cleanups}")
            print(f"Uptime: {status.uptime_seconds:.2f} seconds")
            if status.last_error:
                print(f"Last error: {status.last_error}")
            return
        
        if args.manual_cleanup:
            # Run manual cleanup and exit
            result = await scheduler.run_manual_cleanup(args.data_types)
            print(f"Manual cleanup result: {result}")
            return
        
        if args.daemon:
            # Run as daemon
            await scheduler.start()
            
            # Keep running until interrupted
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down scheduler...")
                await scheduler.stop()
        else:
            print("Use --daemon to run continuously or --manual-cleanup for one-time cleanup")
            
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    asyncio.run(main())
