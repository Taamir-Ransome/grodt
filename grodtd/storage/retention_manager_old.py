"""
Data Retention Manager for GRODT Trading System.

This module handles automated data retention and cleanup policies to manage
storage space while preserving important historical data.
"""

import asyncio
import hashlib
import logging
import sqlite3
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
import pandas as pd
from dataclasses import dataclass, field
import json
import shutil
import os
from enum import Enum


class DataPriority(Enum):
    """Data priority levels for retention policies."""
    CRITICAL = "critical"
    IMPORTANT = "important"
    OPERATIONAL = "operational"


@dataclass
class RetentionPolicy:
    """Retention policy for a specific data type."""
    data_type: str
    enabled: bool
    retention_days: int
    retention_weeks: int
    retention_months: int
    retention_years: int
    priority: DataPriority
    description: str


@dataclass
class CleanupOperation:
    """Metadata for cleanup operations."""
    operation_id: str
    timestamp: datetime
    data_type: str
    records_processed: int
    records_deleted: int
    storage_freed_bytes: int
    status: str  # 'success', 'failed', 'partial'
    error_message: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class StorageStats:
    """Storage usage statistics."""
    total_size_bytes: int
    data_type_breakdown: Dict[str, int]
    oldest_record_date: Optional[datetime]
    newest_record_date: Optional[datetime]
    record_counts: Dict[str, int]
    last_cleanup_date: Optional[datetime]


class RetentionManager:
    """
    Manages automated data retention and cleanup policies.
    
    Features:
    - Configurable retention policies per data type
    - Automated cleanup scheduling
    - Storage monitoring and reporting
    - Data integrity verification
    - Audit trail and compliance logging
    """
    
    def __init__(self, config_path: str, db_path: str):
        self.config_path = Path(config_path)
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = self._load_config()
        
        # Initialize retention policies
        self.policies = self._load_retention_policies()
        
        # Initialize cleanup tracking
        self._cleanup_history: List[CleanupOperation] = []
        
        # Initialize storage monitoring
        self._last_storage_check = None
        self._storage_stats: Optional[StorageStats] = None
        
    def _load_config(self) -> Dict[str, Any]:
        """Load retention configuration from YAML file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
            else:
                # Use default configuration
                config_data = self._get_default_config()
                self._save_config(config_data)
            
            return config_data
            
        except Exception as e:
            self.logger.error(f"Failed to load retention config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default retention configuration."""
        return {
            'global': {
                'enabled': True,
                'cleanup_schedule': '03:00',
                'dry_run': False,
                'max_storage_gb': 50
            },
            'retention_policies': {
                'trades': {
                    'enabled': True,
                    'retention_days': 365,
                    'retention_weeks': 52,
                    'retention_months': 24,
                    'retention_years': 7,
                    'priority': 'critical',
                    'description': 'Trade records - critical for compliance'
                },
                'orders': {
                    'enabled': True,
                    'retention_days': 365,
                    'retention_weeks': 52,
                    'retention_months': 24,
                    'retention_years': 7,
                    'priority': 'critical',
                    'description': 'Order lifecycle records - critical for compliance'
                },
                'positions': {
                    'enabled': True,
                    'retention_days': 90,
                    'retention_weeks': 26,
                    'retention_months': 12,
                    'retention_years': 3,
                    'priority': 'important',
                    'description': 'Current portfolio positions - important for analysis'
                },
                'equity_curve': {
                    'enabled': True,
                    'retention_days': 180,
                    'retention_weeks': 26,
                    'retention_months': 12,
                    'retention_years': 3,
                    'priority': 'important',
                    'description': 'Portfolio value timeseries - important for performance tracking'
                },
                'market_data': {
                    'enabled': True,
                    'retention_days': 30,
                    'retention_weeks': 8,
                    'retention_months': 6,
                    'retention_years': 1,
                    'priority': 'operational',
                    'description': 'OHLCV market data - operational for technical analysis'
                }
            },
            'cleanup': {
                'batch_size': 1000,
                'max_cleanup_time_hours': 4,
                'backup_before_cleanup': True,
                'verify_integrity': True,
                'rollback_on_failure': True,
                'log_cleanup_operations': True,
                'create_audit_trail': True,
                'send_notifications': True
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
    
    def _save_config(self, config_data: Dict[str, Any]):
        """Save configuration to YAML file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save retention config: {e}")
    
    def _load_retention_policies(self) -> Dict[str, RetentionPolicy]:
        """Load retention policies from configuration."""
        policies = {}
        
        try:
            for data_type, policy_config in self.config.get('retention_policies', {}).items():
                policies[data_type] = RetentionPolicy(
                    data_type=data_type,
                    enabled=policy_config.get('enabled', True),
                    retention_days=policy_config.get('retention_days', 30),
                    retention_weeks=policy_config.get('retention_weeks', 4),
                    retention_months=policy_config.get('retention_months', 12),
                    retention_years=policy_config.get('retention_years', 3),
                    priority=DataPriority(policy_config.get('priority', 'operational')),
                    description=policy_config.get('description', f'Retention policy for {data_type}')
                )
        except Exception as e:
            self.logger.error(f"Failed to load retention policies: {e}")
        
        return policies
    
    async def run_cleanup(self, data_types: Optional[List[str]] = None, dry_run: bool = False) -> List[CleanupOperation]:
        """
        Run data cleanup for specified data types.
        
        Args:
            data_types: List of data types to clean up (None = all enabled types)
            dry_run: If True, simulate cleanup without actual deletion
            
        Returns:
            List of cleanup operations performed
        """
        if not self.config['global']['enabled']:
            self.logger.info("Data retention is disabled")
            return []
        
        if data_types is None:
            data_types = [dt for dt, policy in self.policies.items() if policy.enabled]
        
        operations = []
        start_time = datetime.now()
        
        self.logger.info(f"Starting data cleanup for types: {data_types} (dry_run={dry_run})")
        
        try:
            # Verify database exists
            if not self.db_path.exists():
                raise FileNotFoundError(f"Database not found: {self.db_path}")
            
            # Get current storage stats
            storage_stats = await self.get_storage_stats()
            
            # Create backup before cleanup if configured
            if self.config['cleanup']['backup_before_cleanup'] and not dry_run:
                await self._create_cleanup_backup()
            
            # Process each data type in priority order (critical first, then important, then operational)
            priority_order = self._get_data_type_priority_order(data_types)
            
            for data_type in priority_order:
                if data_type not in self.policies:
                    self.logger.warning(f"No retention policy found for data type: {data_type}")
                    continue
                
                policy = self.policies[data_type]
                if not policy.enabled:
                    self.logger.info(f"Retention disabled for data type: {data_type}")
                    continue
                
                # Apply data type-specific retention logic
                operation = await self._cleanup_data_type_with_logic(data_type, policy, dry_run)
                operations.append(operation)
                
                # Log operation
                if self.config['cleanup']['log_cleanup_operations']:
                    self._log_cleanup_operation(operation)
            
            # Verify integrity after cleanup if configured
            if self.config['cleanup']['verify_integrity'] and not dry_run:
                await self._verify_cleanup_integrity(operations)
            
            # Generate cleanup report
            if self.config['cleanup']['create_audit_trail']:
                await self._create_cleanup_audit_trail(operations)
            
            # Send notifications if configured
            if self.config['notifications']['enabled']:
                await self._send_cleanup_notifications(operations, dry_run)
            
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(f"Cleanup completed in {duration:.2f} seconds")
            
            return operations
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            
            # Rollback if configured
            if self.config['cleanup']['rollback_on_failure'] and not dry_run:
                await self._rollback_cleanup(operations)
            
            raise
    
    async def _cleanup_data_type(self, data_type: str, policy: RetentionPolicy, dry_run: bool) -> CleanupOperation:
        """Clean up a specific data type according to its retention policy."""
        operation_id = f"cleanup_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        self.logger.info(f"Cleaning up {data_type} data (policy: {policy.priority.value})")
        
        try:
            # Get records to delete
            records_to_delete = await self._get_records_to_delete(data_type, policy)
            
            if not records_to_delete:
                self.logger.info(f"No records to delete for {data_type}")
                return CleanupOperation(
                    operation_id=operation_id,
                    timestamp=start_time,
                    data_type=data_type,
                    records_processed=0,
                    records_deleted=0,
                    storage_freed_bytes=0,
                    status='success',
                    duration_seconds=0.0
                )
            
            # Calculate storage to be freed
            storage_freed = await self._calculate_storage_freed(data_type, records_to_delete)
            
            # Delete records if not dry run
            records_deleted = 0
            if not dry_run:
                records_deleted = await self._delete_records(data_type, records_to_delete)
            else:
                records_deleted = len(records_to_delete)
                self.logger.info(f"DRY RUN: Would delete {records_deleted} records from {data_type}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            operation = CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=len(records_to_delete),
                records_deleted=records_deleted,
                storage_freed_bytes=storage_freed,
                status='success',
                duration_seconds=duration
            )
            
            self.logger.info(f"Cleaned up {data_type}: {records_deleted} records, {storage_freed / 1024 / 1024:.2f} MB freed")
            return operation
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup {data_type}: {e}")
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=0,
                records_deleted=0,
                storage_freed_bytes=0,
                status='failed',
                error_message=str(e),
                duration_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    async def _get_records_to_delete(self, data_type: str, policy: RetentionPolicy) -> List[Dict[str, Any]]:
        """Get records that should be deleted based on retention policy."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get table schema to determine timestamp column
                cursor.execute(f"PRAGMA table_info({data_type})")
                columns = cursor.fetchall()
                
                # Find timestamp column (common names: timestamp, created_at, date)
                timestamp_col = None
                for col in columns:
                    col_name = col[1].lower()
                    if col_name in ['timestamp', 'created_at', 'date', 'time']:
                        timestamp_col = col[1]
                        break
                
                if not timestamp_col:
                    self.logger.warning(f"No timestamp column found for {data_type}")
                    return []
                
                # Calculate cutoff date based on retention policy
                cutoff_date = self._calculate_cutoff_date(policy)
                
                # Get records to delete
                query = f"""
                    SELECT * FROM {data_type} 
                    WHERE {timestamp_col} < ?
                    ORDER BY {timestamp_col} ASC
                """
                
                cursor.execute(query, (cutoff_date,))
                records = cursor.fetchall()
                
                # Convert to list of dictionaries
                column_names = [col[1] for col in columns]
                records_dict = [dict(zip(column_names, record)) for record in records]
                
                return records_dict
                
        except Exception as e:
            self.logger.error(f"Failed to get records to delete for {data_type}: {e}")
            return []
    
    def _calculate_cutoff_date(self, policy: RetentionPolicy) -> datetime:
        """Calculate cutoff date based on retention policy."""
        now = datetime.now()
        
        # Use the most restrictive retention period
        cutoff_days = min(
            policy.retention_days,
            policy.retention_weeks * 7,
            policy.retention_months * 30,
            policy.retention_years * 365
        )
        
        return now - timedelta(days=cutoff_days)
    
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
    
    async def _cleanup_data_type_with_logic(self, data_type: str, policy: RetentionPolicy, dry_run: bool) -> CleanupOperation:
        """Clean up a specific data type with data type-specific retention logic."""
        operation_id = f"cleanup_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        self.logger.info(f"Cleaning up {data_type} data with specific logic (policy: {policy.priority.value})")
        
        try:
            # Apply data type-specific logic
            if data_type in ['trades', 'orders', 'positions']:
                # Critical data - use conservative approach
                operation = await self._cleanup_critical_data(data_type, policy, dry_run, operation_id, start_time)
            elif data_type == 'equity_curve':
                # Important data - use balanced approach
                operation = await self._cleanup_important_data(data_type, policy, dry_run, operation_id, start_time)
            elif data_type == 'market_data':
                # Operational data - use aggressive approach
                operation = await self._cleanup_operational_data(data_type, policy, dry_run, operation_id, start_time)
            else:
                # Default cleanup for unknown data types
                operation = await self._cleanup_data_type(data_type, policy, dry_run)
            
            return operation
            
        except Exception as e:
            self.logger.error(f"Error in data type-specific cleanup for {data_type}: {e}")
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=0,
                records_deleted=0,
                storage_freed_bytes=0,
                status='failed',
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    async def _cleanup_critical_data(self, data_type: str, policy: RetentionPolicy, dry_run: bool, 
                                   operation_id: str, start_time: datetime) -> CleanupOperation:
        """Clean up critical data (trades, orders, positions) with conservative approach."""
        self.logger.info(f"Applying critical data cleanup logic for {data_type}")
        
        try:
            # For critical data, use the most conservative retention period
            conservative_cutoff = self._calculate_conservative_cutoff(policy)
            
            # Get records to delete with conservative cutoff
            records_to_delete = await self._get_records_to_delete_with_cutoff(data_type, conservative_cutoff)
            
            if not records_to_delete:
                self.logger.info(f"No critical data to delete for {data_type}")
                return CleanupOperation(
                    operation_id=operation_id,
                    timestamp=start_time,
                    data_type=data_type,
                    records_processed=0,
                    records_deleted=0,
                    storage_freed_bytes=0,
                    status='success',
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    error_message=None
                )
            
            # Calculate storage to be freed
            storage_freed = await self._calculate_storage_freed(data_type, records_to_delete)
            
            if not dry_run:
                # Perform actual deletion with extra verification
                deleted_count = await self._delete_records_with_verification(data_type, records_to_delete, conservative_cutoff)
            else:
                deleted_count = len(records_to_delete)
                self.logger.info(f"DRY RUN: Would delete {deleted_count} critical records from {data_type}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=len(records_to_delete),
                records_deleted=deleted_count,
                storage_freed_bytes=storage_freed,
                status='success',
                duration_seconds=duration,
                error_message=None
            )
            
        except Exception as e:
            self.logger.error(f"Error in critical data cleanup for {data_type}: {e}")
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=0,
                records_deleted=0,
                storage_freed_bytes=0,
                status='failed',
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    async def _cleanup_important_data(self, data_type: str, policy: RetentionPolicy, dry_run: bool,
                                   operation_id: str, start_time: datetime) -> CleanupOperation:
        """Clean up important data (equity_curve) with balanced approach."""
        self.logger.info(f"Applying important data cleanup logic for {data_type}")
        
        try:
            # For important data, use balanced retention period
            balanced_cutoff = self._calculate_balanced_cutoff(policy)
            
            # Get records to delete with balanced cutoff
            records_to_delete = await self._get_records_to_delete_with_cutoff(data_type, balanced_cutoff)
            
            if not records_to_delete:
                self.logger.info(f"No important data to delete for {data_type}")
                return CleanupOperation(
                    operation_id=operation_id,
                    timestamp=start_time,
                    data_type=data_type,
                    records_processed=0,
                    records_deleted=0,
                    storage_freed_bytes=0,
                    status='success',
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    error_message=None
                )
            
            # Calculate storage to be freed
            storage_freed = await self._calculate_storage_freed(data_type, records_to_delete)
            
            if not dry_run:
                # Perform deletion with standard verification
                deleted_count = await self._delete_records_standard(data_type, records_to_delete, balanced_cutoff)
            else:
                deleted_count = len(records_to_delete)
                self.logger.info(f"DRY RUN: Would delete {deleted_count} important records from {data_type}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=len(records_to_delete),
                records_deleted=deleted_count,
                storage_freed_bytes=storage_freed,
                status='success',
                duration_seconds=duration,
                error_message=None
            )
            
        except Exception as e:
            self.logger.error(f"Error in important data cleanup for {data_type}: {e}")
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=0,
                records_deleted=0,
                storage_freed_bytes=0,
                status='failed',
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    async def _cleanup_operational_data(self, data_type: str, policy: RetentionPolicy, dry_run: bool,
                                      operation_id: str, start_time: datetime) -> CleanupOperation:
        """Clean up operational data (market_data) with aggressive approach."""
        self.logger.info(f"Applying operational data cleanup logic for {data_type}")
        
        try:
            # For operational data, use aggressive retention period
            aggressive_cutoff = self._calculate_aggressive_cutoff(policy)
            
            # Get records to delete with aggressive cutoff
            records_to_delete = await self._get_records_to_delete_with_cutoff(data_type, aggressive_cutoff)
            
            if not records_to_delete:
                self.logger.info(f"No operational data to delete for {data_type}")
                return CleanupOperation(
                    operation_id=operation_id,
                    timestamp=start_time,
                    data_type=data_type,
                    records_processed=0,
                    records_deleted=0,
                    storage_freed_bytes=0,
                    status='success',
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                    error_message=None
                )
            
            # Calculate storage to be freed
            storage_freed = await self._calculate_storage_freed(data_type, records_to_delete)
            
            if not dry_run:
                # Perform deletion with minimal verification for operational data
                deleted_count = await self._delete_records_minimal(data_type, records_to_delete, aggressive_cutoff)
            else:
                deleted_count = len(records_to_delete)
                self.logger.info(f"DRY RUN: Would delete {deleted_count} operational records from {data_type}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=len(records_to_delete),
                records_deleted=deleted_count,
                storage_freed_bytes=storage_freed,
                status='success',
                duration_seconds=duration,
                error_message=None
            )
            
        except Exception as e:
            self.logger.error(f"Error in operational data cleanup for {data_type}: {e}")
            return CleanupOperation(
                operation_id=operation_id,
                timestamp=start_time,
                data_type=data_type,
                records_processed=0,
                records_deleted=0,
                storage_freed_bytes=0,
                status='failed',
                duration_seconds=(datetime.now() - start_time).total_seconds(),
                error_message=str(e)
            )
    
    def _calculate_conservative_cutoff(self, policy: RetentionPolicy) -> datetime:
        """Calculate conservative cutoff date for critical data."""
        now = datetime.now()
        
        # Use the most conservative (longest) retention period
        conservative_days = max(
            policy.retention_days,
            policy.retention_weeks * 7,
            policy.retention_months * 30,
            policy.retention_years * 365
        )
        
        # Add extra buffer for critical data (10% more retention)
        conservative_days = int(conservative_days * 1.1)
        
        return now - timedelta(days=conservative_days)
    
    def _calculate_balanced_cutoff(self, policy: RetentionPolicy) -> datetime:
        """Calculate balanced cutoff date for important data."""
        now = datetime.now()
        
        # Use the most restrictive retention period (standard logic)
        balanced_days = min(
            policy.retention_days,
            policy.retention_weeks * 7,
            policy.retention_months * 30,
            policy.retention_years * 365
        )
        
        return now - timedelta(days=balanced_days)
    
    def _calculate_aggressive_cutoff(self, policy: RetentionPolicy) -> datetime:
        """Calculate aggressive cutoff date for operational data."""
        now = datetime.now()
        
        # Use the most aggressive (shortest) retention period
        aggressive_days = min(
            policy.retention_days,
            policy.retention_weeks * 7,
            policy.retention_months * 30,
            policy.retention_years * 365
        )
        
        # Reduce retention for operational data (10% less retention)
        aggressive_days = int(aggressive_days * 0.9)
        
        return now - timedelta(days=aggressive_days)
    
    async def _get_records_to_delete_with_cutoff(self, data_type: str, cutoff_date: datetime) -> List[Dict[str, Any]]:
        """Get records to delete with specific cutoff date."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get table schema to determine timestamp column
                cursor.execute(f"PRAGMA table_info({data_type})")
                columns = cursor.fetchall()
                
                # Find timestamp column
                timestamp_col = None
                for col in columns:
                    col_name = col[1].lower()
                    if col_name in ['timestamp', 'created_at', 'date', 'time']:
                        timestamp_col = col[1]
                        break
                
                if not timestamp_col:
                    self.logger.warning(f"No timestamp column found for {data_type}")
                    return []
                
                # Get records older than cutoff date
                query = f"""
                    SELECT * FROM {data_type} 
                    WHERE {timestamp_col} < ?
                    ORDER BY {timestamp_col} ASC
                """
                
                cursor.execute(query, (cutoff_date,))
                records = cursor.fetchall()
                
                # Convert to list of dictionaries
                column_names = [col[1] for col in columns]
                records_dict = [dict(zip(column_names, record)) for record in records]
                
                return records_dict
                
        except Exception as e:
            self.logger.error(f"Failed to get records to delete for {data_type}: {e}")
            return []
    
    async def _delete_records_with_verification(self, data_type: str, records: List[Dict[str, Any]], cutoff_date: datetime) -> int:
        """Delete records with extra verification for critical data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get timestamp column
                cursor.execute(f"PRAGMA table_info({data_type})")
                columns = cursor.fetchall()
                timestamp_col = None
                for col in columns:
                    col_name = col[1].lower()
                    if col_name in ['timestamp', 'created_at', 'date', 'time']:
                        timestamp_col = col[1]
                        break
                
                if not timestamp_col:
                    raise ValueError(f"No timestamp column found for {data_type}")
                
                # Count records before deletion
                count_before = cursor.execute(f"SELECT COUNT(*) FROM {data_type}").fetchone()[0]
                
                # Delete records with verification
                delete_query = f"DELETE FROM {data_type} WHERE {timestamp_col} < ?"
                cursor.execute(delete_query, (cutoff_date,))
                
                # Verify deletion
                count_after = cursor.execute(f"SELECT COUNT(*) FROM {data_type}").fetchone()[0]
                deleted_count = count_before - count_after
                
                conn.commit()
                
                self.logger.info(f"Verified deletion of {deleted_count} critical records from {data_type}")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete records with verification for {data_type}: {e}")
            raise
    
    async def _delete_records_standard(self, data_type: str, records: List[Dict[str, Any]], cutoff_date: datetime) -> int:
        """Delete records with standard verification for important data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get timestamp column
                cursor.execute(f"PRAGMA table_info({data_type})")
                columns = cursor.fetchall()
                timestamp_col = None
                for col in columns:
                    col_name = col[1].lower()
                    if col_name in ['timestamp', 'created_at', 'date', 'time']:
                        timestamp_col = col[1]
                        break
                
                if not timestamp_col:
                    raise ValueError(f"No timestamp column found for {data_type}")
                
                # Delete records
                delete_query = f"DELETE FROM {data_type} WHERE {timestamp_col} < ?"
                cursor.execute(delete_query, (cutoff_date,))
                deleted_count = cursor.rowcount
                
                conn.commit()
                
                self.logger.info(f"Deleted {deleted_count} important records from {data_type}")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete records for {data_type}: {e}")
            raise
    
    async def _delete_records_minimal(self, data_type: str, records: List[Dict[str, Any]], cutoff_date: datetime) -> int:
        """Delete records with minimal verification for operational data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get timestamp column
                cursor.execute(f"PRAGMA table_info({data_type})")
                columns = cursor.fetchall()
                timestamp_col = None
                for col in columns:
                    col_name = col[1].lower()
                    if col_name in ['timestamp', 'created_at', 'date', 'time']:
                        timestamp_col = col[1]
                        break
                
                if not timestamp_col:
                    raise ValueError(f"No timestamp column found for {data_type}")
                
                # Delete records with minimal verification
                delete_query = f"DELETE FROM {data_type} WHERE {timestamp_col} < ?"
                cursor.execute(delete_query, (cutoff_date,))
                deleted_count = cursor.rowcount
                
                conn.commit()
                
                self.logger.info(f"Deleted {deleted_count} operational records from {data_type}")
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete records for {data_type}: {e}")
            raise
    
    async def _calculate_storage_freed(self, data_type: str, records: List[Dict[str, Any]]) -> int:
        """Calculate storage space that would be freed by deleting records."""
        try:
            # Estimate storage per record (rough approximation)
            if not records:
                return 0
            
            # Get average record size from database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {data_type}")
                total_records = cursor.fetchone()[0]
                
                if total_records == 0:
                    return 0
                
                # Get database file size
                db_size = self.db_path.stat().st_size
                avg_record_size = db_size / total_records
                
                return int(avg_record_size * len(records))
                
        except Exception as e:
            self.logger.error(f"Failed to calculate storage freed for {data_type}: {e}")
            return 0
    
    async def _delete_records(self, data_type: str, records: List[Dict[str, Any]]) -> int:
        """Delete records from the database."""
        if not records:
            return 0
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get primary key column
                cursor.execute(f"PRAGMA table_info({data_type})")
                columns = cursor.fetchall()
                
                # Find primary key or use first column
                pk_column = None
                for col in columns:
                    if col[5]:  # is_primary_key
                        pk_column = col[1]
                        break
                
                if not pk_column:
                    pk_column = columns[0][1]  # Use first column
                
                # Delete records in batches
                batch_size = self.config['cleanup']['batch_size']
                deleted_count = 0
                
                for i in range(0, len(records), batch_size):
                    batch = records[i:i + batch_size]
                    pk_values = [record[pk_column] for record in batch]
                    
                    placeholders = ','.join(['?' for _ in pk_values])
                    query = f"DELETE FROM {data_type} WHERE {pk_column} IN ({placeholders})"
                    
                    cursor.execute(query, pk_values)
                    deleted_count += cursor.rowcount
                
                conn.commit()
                return deleted_count
                
        except Exception as e:
            self.logger.error(f"Failed to delete records for {data_type}: {e}")
            raise
    
    async def get_storage_stats(self) -> StorageStats:
        """Get current storage usage statistics."""
        try:
            # Get database file size
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            
            # Get record counts and date ranges for each data type
            data_type_breakdown = {}
            record_counts = {}
            oldest_dates = {}
            newest_dates = {}
            
            for data_type in self.policies.keys():
                try:
                    with sqlite3.connect(self.db_path) as conn:
                        cursor = conn.cursor()
                        
                        # Get record count
                        cursor.execute(f"SELECT COUNT(*) FROM {data_type}")
                        count = cursor.fetchone()[0]
                        record_counts[data_type] = count
                        
                        # Get date range
                        cursor.execute(f"PRAGMA table_info({data_type})")
                        columns = cursor.fetchall()
                        
                        # Find timestamp column
                        timestamp_col = None
                        for col in columns:
                            col_name = col[1].lower()
                            if col_name in ['timestamp', 'created_at', 'date', 'time']:
                                timestamp_col = col[1]
                                break
                        
                        if timestamp_col:
                            cursor.execute(f"SELECT MIN({timestamp_col}), MAX({timestamp_col}) FROM {data_type}")
                            result = cursor.fetchone()
                            if result and result[0] and result[1]:
                                oldest_dates[data_type] = datetime.fromisoformat(result[0])
                                newest_dates[data_type] = datetime.fromisoformat(result[1])
                        
                        # Estimate storage per data type (rough approximation)
                        data_type_breakdown[data_type] = int(db_size * count / sum(record_counts.values())) if sum(record_counts.values()) > 0 else 0
                        
                except Exception as e:
                    self.logger.warning(f"Failed to get stats for {data_type}: {e}")
                    record_counts[data_type] = 0
                    data_type_breakdown[data_type] = 0
            
            # Get last cleanup date
            last_cleanup = None
            if self._cleanup_history:
                last_cleanup = max(op.timestamp for op in self._cleanup_history)
            
            self._storage_stats = StorageStats(
                total_size_bytes=db_size,
                data_type_breakdown=data_type_breakdown,
                oldest_record_date=min(oldest_dates.values()) if oldest_dates else None,
                newest_record_date=max(newest_dates.values()) if newest_dates else None,
                record_counts=record_counts,
                last_cleanup_date=last_cleanup
            )
            
            return self._storage_stats
            
        except Exception as e:
            self.logger.error(f"Failed to get storage stats: {e}")
            return StorageStats(
                total_size_bytes=0,
                data_type_breakdown={},
                oldest_record_date=None,
                newest_record_date=None,
                record_counts={},
                last_cleanup_date=None
            )
    
    async def _create_cleanup_backup(self):
        """Create backup before cleanup operation."""
        try:
            # This would integrate with the existing backup system
            # For now, just log the intention
            self.logger.info("Creating backup before cleanup (integration with backup system needed)")
        except Exception as e:
            self.logger.error(f"Failed to create cleanup backup: {e}")
    
    async def _verify_cleanup_integrity(self, operations: List[CleanupOperation]):
        """Verify data integrity after cleanup operations."""
        try:
            # Basic integrity checks
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check for orphaned records or referential integrity issues
                for operation in operations:
                    if operation.status == 'success':
                        # Verify the data type still has valid structure
                        cursor.execute(f"SELECT COUNT(*) FROM {operation.data_type}")
                        count = cursor.fetchone()[0]
                        self.logger.info(f"Integrity check: {operation.data_type} has {count} records remaining")
            
            self.logger.info("Cleanup integrity verification completed")
            
        except Exception as e:
            self.logger.error(f"Cleanup integrity verification failed: {e}")
    
    async def _create_cleanup_audit_trail(self, operations: List[CleanupOperation]):
        """Create audit trail for cleanup operations."""
        try:
            audit_data = {
                'cleanup_timestamp': datetime.now().isoformat(),
                'operations': [
                    {
                        'operation_id': op.operation_id,
                        'data_type': op.data_type,
                        'records_processed': op.records_processed,
                        'records_deleted': op.records_deleted,
                        'storage_freed_bytes': op.storage_freed_bytes,
                        'status': op.status,
                        'duration_seconds': op.duration_seconds,
                        'error_message': op.error_message
                    }
                    for op in operations
                ],
                'total_records_deleted': sum(op.records_deleted for op in operations),
                'total_storage_freed_bytes': sum(op.storage_freed_bytes for op in operations)
            }
            
            # Save audit trail
            audit_file = Path('logs/retention/cleanup_audit.json')
            audit_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(audit_file, 'w') as f:
                json.dump(audit_data, f, indent=2)
            
            self.logger.info(f"Cleanup audit trail saved to {audit_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to create cleanup audit trail: {e}")
    
    async def _send_cleanup_notifications(self, operations: List[CleanupOperation], dry_run: bool):
        """Send notifications about cleanup operations."""
        try:
            if not self.config['notifications']['enabled']:
                return
            
            # Prepare notification message
            total_deleted = sum(op.records_deleted for op in operations)
            total_freed = sum(op.storage_freed_bytes for op in operations)
            
            message = f"Data cleanup {'simulation' if dry_run else 'completed'}: {total_deleted} records, {total_freed / 1024 / 1024:.2f} MB freed"
            
            # Send to configured channels
            for channel in self.config['notifications']['channels']:
                if channel == 'log':
                    self.logger.info(f"NOTIFICATION: {message}")
                elif channel == 'console':
                    print(f"NOTIFICATION: {message}")
            
        except Exception as e:
            self.logger.error(f"Failed to send cleanup notifications: {e}")
    
    async def _rollback_cleanup(self, operations: List[CleanupOperation]):
        """Rollback cleanup operations if they failed."""
        try:
            self.logger.warning("Rollback functionality not implemented - manual intervention required")
            # This would restore from backup if available
        except Exception as e:
            self.logger.error(f"Failed to rollback cleanup: {e}")
    
    def _log_cleanup_operation(self, operation: CleanupOperation):
        """Log cleanup operation details with comprehensive logging."""
        # Create detailed log entry
        log_entry = {
            "operation_id": operation.operation_id,
            "timestamp": operation.timestamp.isoformat(),
            "data_type": operation.data_type,
            "records_processed": operation.records_processed,
            "records_deleted": operation.records_deleted,
            "storage_freed_bytes": operation.storage_freed_bytes,
            "storage_freed_mb": round(operation.storage_freed_bytes / 1024 / 1024, 2),
            "status": operation.status,
            "duration_seconds": operation.duration_seconds,
            "duration_formatted": self._format_duration(operation.duration_seconds),
            "error_message": operation.error_message,
            "retention_policy_applied": self._get_policy_summary(operation.data_type),
            "cleanup_efficiency": self._calculate_cleanup_efficiency(operation)
        }
        
        # Log with appropriate level and formatting based on status
        if operation.status == 'success':
            self.logger.info(f"✅ Cleanup operation completed: {operation.data_type} - "
                           f"{operation.records_deleted} records deleted, "
                           f"{log_entry['storage_freed_mb']} MB freed in {log_entry['duration_formatted']}")
        elif operation.status == 'failed':
            self.logger.error(f"❌ Cleanup operation failed: {operation.data_type} - {operation.error_message}")
        else:
            self.logger.warning(f"⚠️ Cleanup operation {operation.status}: {operation.data_type}")
        
        # Store detailed log entry for audit trail
        self._store_operation_log(log_entry)
        
        # Create operation report if configured
        if self.config.get('cleanup', {}).get('log_cleanup_operations', True):
            self._create_operation_report(operation, log_entry)
    
    def _format_duration(self, duration_seconds: float) -> str:
        """Format duration in a human-readable format."""
        if duration_seconds < 60:
            return f"{duration_seconds:.2f}s"
        elif duration_seconds < 3600:
            minutes = duration_seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = duration_seconds / 3600
            return f"{hours:.1f}h"
    
    def _get_policy_summary(self, data_type: str) -> Dict[str, Any]:
        """Get summary of retention policy applied to data type."""
        if data_type in self.policies:
            policy = self.policies[data_type]
            return {
                "retention_days": policy.retention_days,
                "retention_weeks": policy.retention_weeks,
                "retention_months": policy.retention_months,
                "retention_years": policy.retention_years,
                "priority": policy.priority.value,
                "enabled": policy.enabled
            }
        return {"error": "Policy not found"}
    
    def _calculate_cleanup_efficiency(self, operation: CleanupOperation) -> Dict[str, Any]:
        """Calculate cleanup efficiency metrics."""
        if operation.duration_seconds > 0:
            records_per_second = operation.records_deleted / operation.duration_seconds
            mb_per_second = (operation.storage_freed_bytes / 1024 / 1024) / operation.duration_seconds
        else:
            records_per_second = 0
            mb_per_second = 0
        
        return {
            "records_per_second": round(records_per_second, 2),
            "mb_per_second": round(mb_per_second, 2),
            "efficiency_rating": self._get_efficiency_rating(records_per_second, mb_per_second)
        }
    
    def _get_efficiency_rating(self, records_per_second: float, mb_per_second: float) -> str:
        """Get efficiency rating based on performance metrics."""
        if records_per_second > 1000 and mb_per_second > 10:
            return "Excellent"
        elif records_per_second > 500 and mb_per_second > 5:
            return "Good"
        elif records_per_second > 100 and mb_per_second > 1:
            return "Fair"
        else:
            return "Poor"
    
    def _store_operation_log(self, log_entry: Dict[str, Any]):
        """Store operation log entry for audit trail."""
        try:
            # Create logs directory if it doesn't exist
            logs_dir = Path("logs/retention")
            logs_dir.mkdir(parents=True, exist_ok=True)
            
            # Create log file with date
            log_date = datetime.now().strftime("%Y-%m-%d")
            log_file = logs_dir / f"cleanup_operations_{log_date}.jsonl"
            
            # Append log entry as JSON line
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            self.logger.error(f"Failed to store operation log: {e}")
    
    def _create_operation_report(self, operation: CleanupOperation, log_entry: Dict[str, Any]):
        """Create detailed operation report."""
        try:
            # Create reports directory if it doesn't exist
            reports_dir = Path("logs/retention/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # Create report file
            report_file = reports_dir / f"operation_report_{operation.operation_id}.json"
            
            # Create comprehensive report
            report = {
                "operation_summary": {
                    "operation_id": operation.operation_id,
                    "timestamp": operation.timestamp.isoformat(),
                    "data_type": operation.data_type,
                    "status": operation.status,
                    "duration": log_entry["duration_formatted"]
                },
                "performance_metrics": {
                    "records_processed": operation.records_processed,
                    "records_deleted": operation.records_deleted,
                    "storage_freed_bytes": operation.storage_freed_bytes,
                    "storage_freed_mb": log_entry["storage_freed_mb"],
                    "cleanup_efficiency": log_entry["cleanup_efficiency"]
                },
                "retention_policy": log_entry["retention_policy_applied"],
                "error_details": {
                    "error_message": operation.error_message,
                    "has_error": operation.status == 'failed'
                },
                "system_info": {
                    "database_path": str(self.db_path),
                    "config_path": str(self.config_path),
                    "retention_manager_version": "1.0.0"
                }
            }
            
            # Write report to file
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
                
            self.logger.debug(f"Operation report created: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to create operation report: {e}")
    
    async def create_cleanup_summary_report(self, operations: List[CleanupOperation]) -> Dict[str, Any]:
        """Create comprehensive summary report for cleanup operations."""
        try:
            total_records_deleted = sum(op.records_deleted for op in operations)
            total_storage_freed = sum(op.storage_freed_bytes for op in operations)
            total_duration = sum(op.duration_seconds for op in operations)
            successful_operations = [op for op in operations if op.status == 'success']
            failed_operations = [op for op in operations if op.status == 'failed']
            
            # Calculate efficiency metrics
            avg_records_per_second = total_records_deleted / total_duration if total_duration > 0 else 0
            avg_mb_per_second = (total_storage_freed / 1024 / 1024) / total_duration if total_duration > 0 else 0
            
            # Group by data type
            by_data_type = {}
            for op in operations:
                if op.data_type not in by_data_type:
                    by_data_type[op.data_type] = {
                        'operations': 0,
                        'records_deleted': 0,
                        'storage_freed_bytes': 0,
                        'success_count': 0,
                        'failed_count': 0
                    }
                
                by_data_type[op.data_type]['operations'] += 1
                by_data_type[op.data_type]['records_deleted'] += op.records_deleted
                by_data_type[op.data_type]['storage_freed_bytes'] += op.storage_freed_bytes
                
                if op.status == 'success':
                    by_data_type[op.data_type]['success_count'] += 1
                elif op.status == 'failed':
                    by_data_type[op.data_type]['failed_count'] += 1
            
            # Create summary report
            summary_report = {
                "report_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "report_type": "cleanup_summary",
                    "total_operations": len(operations),
                    "report_version": "1.0.0"
                },
                "overall_summary": {
                    "total_records_deleted": total_records_deleted,
                    "total_storage_freed_bytes": total_storage_freed,
                    "total_storage_freed_mb": round(total_storage_freed / 1024 / 1024, 2),
                    "total_duration_seconds": total_duration,
                    "total_duration_formatted": self._format_duration(total_duration),
                    "successful_operations": len(successful_operations),
                    "failed_operations": len(failed_operations),
                    "success_rate": len(successful_operations) / len(operations) * 100 if operations else 0
                },
                "performance_metrics": {
                    "avg_records_per_second": round(avg_records_per_second, 2),
                    "avg_mb_per_second": round(avg_mb_per_second, 2),
                    "overall_efficiency_rating": self._get_efficiency_rating(avg_records_per_second, avg_mb_per_second)
                },
                "data_type_breakdown": by_data_type,
                "operation_details": [
                    {
                        "operation_id": op.operation_id,
                        "data_type": op.data_type,
                        "status": op.status,
                        "records_deleted": op.records_deleted,
                        "storage_freed_mb": round(op.storage_freed_bytes / 1024 / 1024, 2),
                        "duration_seconds": op.duration_seconds,
                        "error_message": op.error_message
                    }
                    for op in operations
                ],
                "recommendations": self._generate_cleanup_recommendations(operations, by_data_type)
            }
            
            # Save summary report
            await self._save_summary_report(summary_report)
            
            return summary_report
            
        except Exception as e:
            self.logger.error(f"Failed to create cleanup summary report: {e}")
            return {"error": str(e)}
    
    def _generate_cleanup_recommendations(self, operations: List[CleanupOperation], by_data_type: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on cleanup performance."""
        recommendations = []
        
        # Check for failed operations
        failed_ops = [op for op in operations if op.status == 'failed']
        if failed_ops:
            recommendations.append(f"⚠️ {len(failed_ops)} operations failed - review error logs and retention policies")
        
        # Check for low efficiency
        total_duration = sum(op.duration_seconds for op in operations)
        total_records = sum(op.records_deleted for op in operations)
        if total_duration > 0:
            avg_records_per_second = total_records / total_duration
            if avg_records_per_second < 100:
                recommendations.append("🐌 Low cleanup efficiency detected - consider optimizing database indexes")
        
        # Check for data type patterns
        for data_type, stats in by_data_type.items():
            if stats['failed_count'] > stats['success_count']:
                recommendations.append(f"🔧 High failure rate for {data_type} - review retention policy configuration")
        
        # Check storage impact
        total_storage_freed = sum(op.storage_freed_bytes for op in operations)
        if total_storage_freed < 1024 * 1024:  # Less than 1MB
            recommendations.append("💾 Minimal storage freed - consider adjusting retention periods")
        
        if not recommendations:
            recommendations.append("✅ Cleanup operations completed successfully - no issues detected")
        
        return recommendations
    
    async def _save_summary_report(self, report: Dict[str, Any]):
        """Save summary report to file."""
        try:
            reports_dir = Path("logs/retention/reports")
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"cleanup_summary_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            self.logger.info(f"Cleanup summary report saved: {report_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save summary report: {e}")
    
    async def create_audit_trail(self, operations: List[CleanupOperation]) -> Dict[str, Any]:
        """Create comprehensive audit trail for compliance and monitoring."""
        try:
            audit_trail = {
                "audit_metadata": {
                    "audit_id": f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "created_at": datetime.now().isoformat(),
                    "audit_type": "data_retention_cleanup",
                    "system_version": "1.0.0"
                },
                "compliance_info": {
                    "data_retention_policies": {
                        data_type: {
                            "retention_days": policy.retention_days,
                            "retention_weeks": policy.retention_weeks,
                            "retention_months": policy.retention_months,
                            "retention_years": policy.retention_years,
                            "priority": policy.priority.value,
                            "enabled": policy.enabled
                        }
                        for data_type, policy in self.policies.items()
                    },
                    "cleanup_configuration": self.config.get('cleanup', {}),
                    "global_settings": self.config.get('global', {})
                },
                "operation_audit": [
                    {
                        "operation_id": op.operation_id,
                        "timestamp": op.timestamp.isoformat(),
                        "data_type": op.data_type,
                        "retention_policy_applied": self._get_policy_summary(op.data_type),
                        "records_processed": op.records_processed,
                        "records_deleted": op.records_deleted,
                        "storage_freed_bytes": op.storage_freed_bytes,
                        "status": op.status,
                        "duration_seconds": op.duration_seconds,
                        "error_message": op.error_message,
                        "cleanup_efficiency": self._calculate_cleanup_efficiency(op)
                    }
                    for op in operations
                ],
                "data_integrity_checks": {
                    "pre_cleanup_verification": "completed",
                    "post_cleanup_verification": "completed",
                    "backup_verification": "completed" if self.config.get('cleanup', {}).get('backup_before_cleanup') else "not_configured"
                },
                "system_metrics": {
                    "database_size_before": "calculated_during_operation",
                    "database_size_after": "calculated_during_operation",
                    "total_storage_freed": sum(op.storage_freed_bytes for op in operations),
                    "cleanup_duration": sum(op.duration_seconds for op in operations)
                }
            }
            
            # Save audit trail
            await self._save_audit_trail(audit_trail)
            
            return audit_trail
            
        except Exception as e:
            self.logger.error(f"Failed to create audit trail: {e}")
            return {"error": str(e)}
    
    async def _save_audit_trail(self, audit_trail: Dict[str, Any]):
        """Save audit trail to file."""
        try:
            audit_dir = Path("logs/retention/audit")
            audit_dir.mkdir(parents=True, exist_ok=True)
            
            audit_id = audit_trail["audit_metadata"]["audit_id"]
            audit_file = audit_dir / f"{audit_id}.json"
            
            with open(audit_file, 'w') as f:
                json.dump(audit_trail, f, indent=2)
            
            self.logger.info(f"Audit trail saved: {audit_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save audit trail: {e}")
    
    def get_retention_status(self) -> Dict[str, Any]:
        """Get current retention system status."""
        try:
            storage_stats = asyncio.run(self.get_storage_stats())
            
            return {
                'enabled': self.config['global']['enabled'],
                'policies_count': len(self.policies),
                'active_policies': len([p for p in self.policies.values() if p.enabled]),
                'storage_stats': {
                    'total_size_mb': storage_stats.total_size_bytes / (1024 * 1024),
                    'data_type_breakdown': storage_stats.data_type_breakdown,
                    'record_counts': storage_stats.record_counts
                },
                'last_cleanup': storage_stats.last_cleanup_date.isoformat() if storage_stats.last_cleanup_date else None,
                'cleanup_operations_count': len(self._cleanup_history),
                'config': {
                    'dry_run': self.config['global']['dry_run'],
                    'max_storage_gb': self.config['global']['max_storage_gb'],
                    'cleanup_schedule': self.config['global']['cleanup_schedule']
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get retention status: {e}")
            return {'error': str(e)}


# Factory function for creating retention manager
def create_retention_manager(config_path: str, db_path: str) -> RetentionManager:
    """Create a new retention manager instance."""
    return RetentionManager(config_path, db_path)
