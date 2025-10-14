"""
Core cleanup logic for the retention system.

This module handles the actual data cleanup operations with data type-specific logic.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from .retention_models import CleanupOperation, RetentionPolicy, DataPriority
except ImportError:
    from retention_models import CleanupOperation, RetentionPolicy, DataPriority

logger = logging.getLogger(__name__)


class RetentionCleanup:
    """Handles data cleanup operations with type-specific logic."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
    
    async def cleanup_data_type_with_logic(self, data_type: str, policy: RetentionPolicy, dry_run: bool = False) -> CleanupOperation:
        """Clean up a specific data type with data type-specific retention logic."""
        operation_id = f"cleanup_{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        start_time = datetime.now()
        
        logger.info(f"Cleaning up {data_type} data with specific logic (policy: {policy.priority.value})")
        
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
                operation = await self._cleanup_data_type_default(data_type, policy, dry_run, operation_id, start_time)
            
            return operation
            
        except Exception as e:
            logger.error(f"Error in data type-specific cleanup for {data_type}: {e}")
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
        logger.info(f"Applying critical data cleanup logic for {data_type}")
        
        try:
            # For critical data, use the most conservative retention period
            conservative_cutoff = self._calculate_conservative_cutoff(policy)
            
            # Get records to delete with conservative cutoff
            records_to_delete = await self._get_records_to_delete_with_cutoff(data_type, conservative_cutoff)
            
            if not records_to_delete:
                logger.info(f"No critical data to delete for {data_type}")
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
                logger.info(f"DRY RUN: Would delete {deleted_count} critical records from {data_type}")
            
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
            logger.error(f"Error in critical data cleanup for {data_type}: {e}")
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
        logger.info(f"Applying important data cleanup logic for {data_type}")
        
        try:
            # For important data, use balanced retention period
            balanced_cutoff = self._calculate_balanced_cutoff(policy)
            
            # Get records to delete with balanced cutoff
            records_to_delete = await self._get_records_to_delete_with_cutoff(data_type, balanced_cutoff)
            
            if not records_to_delete:
                logger.info(f"No important data to delete for {data_type}")
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
                logger.info(f"DRY RUN: Would delete {deleted_count} important records from {data_type}")
            
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
            logger.error(f"Error in important data cleanup for {data_type}: {e}")
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
        logger.info(f"Applying operational data cleanup logic for {data_type}")
        
        try:
            # For operational data, use aggressive retention period
            aggressive_cutoff = self._calculate_aggressive_cutoff(policy)
            
            # Get records to delete with aggressive cutoff
            records_to_delete = await self._get_records_to_delete_with_cutoff(data_type, aggressive_cutoff)
            
            if not records_to_delete:
                logger.info(f"No operational data to delete for {data_type}")
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
                logger.info(f"DRY RUN: Would delete {deleted_count} operational records from {data_type}")
            
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
            logger.error(f"Error in operational data cleanup for {data_type}: {e}")
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
    
    async def _cleanup_data_type_default(self, data_type: str, policy: RetentionPolicy, dry_run: bool,
                                       operation_id: str, start_time: datetime) -> CleanupOperation:
        """Default cleanup for unknown data types."""
        logger.info(f"Applying default cleanup logic for {data_type}")
        
        try:
            # Use standard cutoff calculation
            cutoff = self._calculate_standard_cutoff(policy)
            
            # Get records to delete
            records_to_delete = await self._get_records_to_delete_with_cutoff(data_type, cutoff)
            
            if not records_to_delete:
                logger.info(f"No data to delete for {data_type}")
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
                # Perform standard deletion
                deleted_count = await self._delete_records_standard(data_type, records_to_delete, cutoff)
            else:
                deleted_count = len(records_to_delete)
                logger.info(f"DRY RUN: Would delete {deleted_count} records from {data_type}")
            
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
            logger.error(f"Error in default cleanup for {data_type}: {e}")
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
    
    def _calculate_standard_cutoff(self, policy: RetentionPolicy) -> datetime:
        """Calculate standard cutoff date."""
        now = datetime.now()
        
        # Use the most restrictive retention period
        cutoff_days = min(
            policy.retention_days,
            policy.retention_weeks * 7,
            policy.retention_months * 30,
            policy.retention_years * 365
        )
        
        return now - timedelta(days=cutoff_days)
    
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
                    logger.warning(f"No timestamp column found for {data_type}")
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
            logger.error(f"Failed to get records to delete for {data_type}: {e}")
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
                
                logger.info(f"Verified deletion of {deleted_count} critical records from {data_type}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to delete records with verification for {data_type}: {e}")
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
                
                logger.info(f"Deleted {deleted_count} important records from {data_type}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to delete records for {data_type}: {e}")
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
                
                logger.info(f"Deleted {deleted_count} operational records from {data_type}")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Failed to delete records for {data_type}: {e}")
            raise
    
    async def _calculate_storage_freed(self, data_type: str, records: List[Dict[str, Any]]) -> int:
        """Calculate storage space that would be freed by deleting records."""
        try:
            # Estimate storage per record (rough approximation)
            if not records:
                return 0
            
            # Calculate average record size
            total_size = 0
            for record in records:
                for key, value in record.items():
                    if isinstance(value, str):
                        total_size += len(value.encode('utf-8'))
                    elif isinstance(value, (int, float)):
                        total_size += 8  # Approximate size for numbers
                    else:
                        total_size += 50  # Default size for other types
            
            avg_record_size = total_size / len(records) if records else 0
            estimated_freed = int(avg_record_size * len(records))
            
            return estimated_freed
            
        except Exception as e:
            logger.error(f"Failed to calculate storage freed for {data_type}: {e}")
            return 0
