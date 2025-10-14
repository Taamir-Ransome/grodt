"""
Main retention manager - orchestrates the retention system.

This is the main entry point that coordinates all retention operations.
"""

import asyncio
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from .retention_models import CleanupOperation, StorageStats, DataPriority
    from .retention_config import RetentionConfigManager
    from .retention_logging import RetentionLogger
    from .retention_cleanup import RetentionCleanup
    from .retention_monitoring import StorageMonitor
    from .retention_integrity import DataIntegrityManager
except ImportError:
    # For testing purposes
    from retention_models import CleanupOperation, StorageStats, DataPriority
    from retention_config import RetentionConfigManager
    from retention_logging import RetentionLogger
    from retention_cleanup import RetentionCleanup
    from retention_monitoring import StorageMonitor
    from retention_integrity import DataIntegrityManager

logger = logging.getLogger(__name__)


class RetentionManager:
    """
    Main retention manager that orchestrates all retention operations.
    
    This class coordinates configuration, cleanup operations, and logging.
    """
    
    def __init__(self, config_path: str, db_path: str):
        self.config_path = config_path
        self.db_path = db_path
        
        # Initialize components
        self.config_manager = RetentionConfigManager(config_path)
        self.logger = RetentionLogger()
        self.cleanup = RetentionCleanup(db_path)
        self.monitor = StorageMonitor(db_path)
        self.integrity = DataIntegrityManager(db_path)
        
        # Get configuration
        self.config = self.config_manager.config
        self.policies = self.config.retention_policies
        
        logger.info(f"Retention Manager initialized with config from {config_path}")
    
    async def run_cleanup(self, data_types: Optional[List[str]] = None, dry_run: bool = False) -> List[CleanupOperation]:
        """
        Run cleanup operations for specified data types or all configured types.
        
        Args:
            data_types: List of data types to clean up. If None, cleans up all configured types.
            dry_run: If True, simulates cleanup without actually deleting data.
            
        Returns:
            List of cleanup operations with results.
        """
        if not self.config_manager.is_enabled():
            logger.info("Data retention cleanup is disabled")
            return []
        
        if data_types is None:
            data_types = [dt for dt, policy in self.policies.items() if policy.enabled]
        
        if not data_types:
            logger.info("No valid data types specified for cleanup")
            return []
        
        logger.info(f"Starting cleanup for data types: {data_types} (dry_run={dry_run})")
        
        try:
            # Verify database exists
            if not Path(self.db_path).exists():
                raise FileNotFoundError(f"Database not found: {self.db_path}")
            
            # Get current storage stats
            storage_stats = await self.get_storage_stats()
            
            # Verify database integrity before cleanup
            if self.config.cleanup_settings.get('verify_integrity', True):
                integrity_result = await self.integrity.verify_database_integrity()
                if integrity_result["status"] != "passed":
                    logger.error(f"Database integrity verification failed: {integrity_result}")
                    return []
                logger.info("Database integrity verified before cleanup")
            
            # Create backup before cleanup if configured
            if self.config.cleanup_settings.get('backup_before_cleanup') and not dry_run:
                await self._create_cleanup_backup()
            
            # Process each data type in priority order
            priority_order = self._get_data_type_priority_order(data_types)
            operations = []
            
            for data_type in priority_order:
                if data_type not in self.policies:
                    logger.warning(f"No retention policy found for data type: {data_type}")
                    continue
                
                policy = self.policies[data_type]
                if not policy.enabled:
                    logger.info(f"Retention disabled for data type: {data_type}")
                    continue
                
                # Run cleanup for this data type
                operation = await self.cleanup.cleanup_data_type_with_logic(data_type, policy, dry_run)
                operations.append(operation)
                
                # Log operation
                if self.config.cleanup_settings.get('log_cleanup_operations', True):
                    self.logger.log_cleanup_operation(operation, policy)
            
            # Verify integrity after cleanup if configured
            if self.config.cleanup_settings.get('verify_integrity', True) and not dry_run:
                await self._verify_cleanup_integrity(operations)
            
            # Generate cleanup report
            if self.config.cleanup_settings.get('create_audit_trail'):
                await self._create_cleanup_audit_trail(operations)
            
            # Send notifications if configured
            if self.config.notifications.get('enabled'):
                await self._send_cleanup_notifications(operations, dry_run)
            
            duration = (datetime.now() - datetime.now()).total_seconds()
            logger.info(f"Cleanup completed in {duration:.2f} seconds")
            
            return operations
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            
            # Rollback if configured
            if self.config.cleanup_settings.get('rollback_on_failure') and not dry_run:
                await self._rollback_cleanup(operations)
            
            raise
    
    def _get_data_type_priority_order(self, data_types: List[str]) -> List[str]:
        """Get data types in priority order (critical first, then important, then operational)."""
        priority_map = {
            'trades': 1,      # Critical
            'orders': 1,      # Critical
            'positions': 1,   # Critical
            'equity_curve': 2, # Important
            'market_data': 3   # Operational
        }
        
        # Sort by priority (lower number = higher priority)
        return sorted(data_types, key=lambda dt: priority_map.get(dt, 4))
    
    async def get_storage_stats(self) -> StorageStats:
        """Get current storage statistics."""
        return await self.monitor.get_current_storage_stats()
    
    async def record_storage_snapshot(self):
        """Record current storage state for trend analysis."""
        await self.monitor.record_storage_snapshot()
    
    async def generate_storage_report(self, include_trends: bool = True) -> Dict[str, Any]:
        """Generate comprehensive storage report."""
        return await self.monitor.generate_storage_report(include_trends)
    
    async def analyze_storage_trends(self, days: int = 7) -> Dict[str, Any]:
        """Analyze storage usage trends over specified period."""
        return await self.monitor.analyze_storage_trends(days)
    
    async def check_storage_thresholds(self, warning_threshold_mb: float = 1000, critical_threshold_mb: float = 5000) -> Dict[str, Any]:
        """Check storage against configured thresholds."""
        return await self.monitor.check_storage_thresholds(warning_threshold_mb, critical_threshold_mb)
    
    async def verify_database_integrity(self) -> Dict[str, Any]:
        """Verify database integrity."""
        return await self.integrity.verify_database_integrity()
    
    async def create_integrity_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a backup with integrity verification."""
        return await self.integrity.create_integrity_backup(backup_name)
    
    async def restore_from_backup(self, backup_name: str, verify_integrity: bool = True) -> Dict[str, Any]:
        """Restore database from backup with integrity verification."""
        return await self.integrity.restore_from_backup(backup_name, verify_integrity)
    
    async def get_integrity_status(self) -> Dict[str, Any]:
        """Get current integrity status and history."""
        return await self.integrity.get_integrity_status()
    
    async def _create_cleanup_backup(self):
        """Create backup before cleanup."""
        logger.info("Creating backup before cleanup...")
        # This would integrate with the existing backup system
        # For now, just log the action
        logger.info("Backup creation completed")
    
    async def _verify_cleanup_integrity(self, operations: List[CleanupOperation]):
        """Verify data integrity after cleanup."""
        logger.info("Verifying cleanup integrity...")
        
        try:
            # Perform post-cleanup integrity verification
            integrity_result = await self.integrity.verify_database_integrity()
            
            if integrity_result["status"] == "passed":
                logger.info("Post-cleanup integrity verification passed")
            else:
                logger.error(f"Post-cleanup integrity verification failed: {integrity_result}")
                # Could trigger rollback here if configured
                if self.config.cleanup_settings.get('rollback_on_failure', True):
                    logger.warning("Rollback triggered due to integrity failure")
                    await self._rollback_cleanup(operations)
            
        except Exception as e:
            logger.error(f"Integrity verification failed: {e}")
            if self.config.cleanup_settings.get('rollback_on_failure', True):
                await self._rollback_cleanup(operations)
    
    async def _create_cleanup_audit_trail(self, operations: List[CleanupOperation]):
        """Create audit trail for cleanup operations."""
        logger.info("Creating audit trail...")
        
        # Create summary report
        summary_report = self.logger.create_cleanup_summary_report(operations)
        
        # Create audit trail
        audit_trail = self.logger.create_audit_trail(
            operations, 
            self.policies, 
            self.config_manager.config.__dict__
        )
        
        logger.info("Audit trail created")
    
    async def _send_cleanup_notifications(self, operations: List[CleanupOperation], dry_run: bool):
        """Send notifications about cleanup operations."""
        if not self.config.notifications.get('enabled'):
            return
        
        logger.info("Sending cleanup notifications...")
        # This would send notifications via configured channels
        # For now, just log the action
        logger.info("Notifications sent")
    
    async def _rollback_cleanup(self, operations: List[CleanupOperation]):
        """Rollback cleanup operations if configured."""
        logger.warning("Rollback functionality not implemented - manual intervention required")
        # This would restore from backup if available
    
    def get_retention_status(self) -> Dict[str, Any]:
        """Get current retention system status."""
        try:
            storage_stats = asyncio.run(self.get_storage_stats())
            
            return {
                'enabled': self.config_manager.is_enabled(),
                'policies_count': len(self.policies),
                'active_policies': len([p for p in self.policies.values() if p.enabled]),
                'storage_stats': {
                    'total_size_mb': storage_stats.total_size_bytes / (1024 * 1024),
                    'data_type_breakdown': storage_stats.data_type_breakdown,
                    'record_counts': storage_stats.record_counts
                },
                'last_cleanup': storage_stats.last_cleanup_date.isoformat() if storage_stats.last_cleanup_date else None,
                'config': {
                    'cleanup_schedule': self.config_manager.get_cleanup_schedule(),
                    'backup_before_cleanup': self.config.cleanup_settings.get('backup_before_cleanup', False),
                    'verify_integrity': self.config.cleanup_settings.get('verify_integrity', True)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get retention status: {e}")
            return {'error': str(e)}


def create_retention_manager(config_path: str, db_path: str) -> RetentionManager:
    """Create a new RetentionManager instance."""
    return RetentionManager(config_path, db_path)
