"""
Backup Manager for GRODT Trading System.

This module handles automated backup and archival of trading data to ensure
data persistence and enable disaster recovery.
"""

import asyncio
import hashlib
import logging
import sqlite3
import yaml
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dataclasses import dataclass
import json
import shutil
import os


@dataclass
class BackupMetadata:
    """Metadata for backup operations."""
    backup_id: str
    timestamp: datetime
    tables_backed_up: List[str]
    total_records: int
    backup_size_bytes: int
    compression_ratio: float
    checksum: str
    status: str  # 'success', 'failed', 'partial'
    error_message: Optional[str] = None


@dataclass
class BackupConfig:
    """Configuration for backup operations."""
    backup_directory: str
    retention_days: int
    retention_weeks: int
    retention_months: int
    retention_years: int
    compression: str  # 'snappy', 'gzip', 'brotli'
    backup_time: str  # 'HH:MM' format
    enabled: bool
    tables_to_backup: List[str]
    verify_integrity: bool
    max_backup_size_mb: int


class BackupManager:
    """
    Manages automated backup and archival of trading data.
    
    Features:
    - Automated nightly backups
    - Parquet format with compression
    - Backup integrity verification
    - Retention policy management
    - Backup restoration capabilities
    """
    
    def __init__(self, config_path: str, db_path: str):
        self.config_path = Path(config_path)
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        
        # Load configuration
        self.config = self._load_config()
        
        # Create backup directory
        self.backup_dir = Path(self.config.backup_directory)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize backup tracking
        self._backup_history: List[BackupMetadata] = []
        
    def _load_config(self) -> BackupConfig:
        """Load backup configuration from YAML file."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
            else:
                # Use default configuration
                config_data = self._get_default_config()
                self._save_config(config_data)
            
            return BackupConfig(**config_data)
            
        except Exception as e:
            self.logger.error(f"Failed to load backup config: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default backup configuration."""
        return {
            'backup_directory': 'data/backups',
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
    
    def _save_config(self, config_data: Dict[str, Any]):
        """Save configuration to YAML file."""
        try:
            with open(self.config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
        except Exception as e:
            self.logger.error(f"Failed to save backup config: {e}")
    
    async def create_backup(self, backup_id: Optional[str] = None) -> BackupMetadata:
        """
        Create a new backup of all trading data.
        
        Args:
            backup_id: Optional custom backup ID
            
        Returns:
            BackupMetadata with backup details
        """
        if backup_id is None:
            backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.info(f"Starting backup: {backup_id}")
        
        try:
            # Verify database exists
            if not self.db_path.exists():
                raise FileNotFoundError(f"Database not found: {self.db_path}")
            
            # Get database statistics
            db_stats = self._get_database_stats()
            
            # Create backup directory for this backup
            backup_path = self.backup_dir / backup_id
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Backup each table
            backed_up_tables = []
            total_records = 0
            
            for table_name in self.config.tables_to_backup:
                if await self._backup_table(table_name, backup_path):
                    backed_up_tables.append(table_name)
                    table_records = db_stats.get(table_name, 0)
                    total_records += table_records
                    self.logger.info(f"Backed up table {table_name}: {table_records} records")
            
            # Create backup metadata
            backup_size = self._calculate_backup_size(backup_path)
            compression_ratio = self._calculate_compression_ratio(backup_size, db_stats)
            checksum = self._calculate_backup_checksum(backup_path)
            
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.now(),
                tables_backed_up=backed_up_tables,
                total_records=total_records,
                backup_size_bytes=backup_size,
                compression_ratio=compression_ratio,
                checksum=checksum,
                status='success'
            )
            
            # Save metadata
            self._save_backup_metadata(backup_path, metadata)
            
            # Verify backup integrity if enabled
            if self.config.verify_integrity:
                if not await self._verify_backup_integrity(backup_path, metadata):
                    metadata.status = 'partial'
                    metadata.error_message = 'Integrity verification failed'
                    self.logger.warning(f"Backup integrity verification failed for {backup_id}")
            
            self._backup_history.append(metadata)
            self.logger.info(f"Backup completed: {backup_id} ({backup_size / 1024 / 1024:.2f} MB)")
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Backup failed: {e}")
            metadata = BackupMetadata(
                backup_id=backup_id,
                timestamp=datetime.now(),
                tables_backed_up=[],
                total_records=0,
                backup_size_bytes=0,
                compression_ratio=0.0,
                checksum='',
                status='failed',
                error_message=str(e)
            )
            self._backup_history.append(metadata)
            return metadata
    
    async def _backup_table(self, table_name: str, backup_path: Path) -> bool:
        """
        Backup a single table to Parquet format.
        
        Args:
            table_name: Name of the table to backup
            backup_path: Directory to store backup files
            
        Returns:
            True if backup successful, False otherwise
        """
        try:
            # Read table data from SQLite
            with sqlite3.connect(self.db_path) as conn:
                query = f"SELECT * FROM {table_name}"
                df = pd.read_sql_query(query, conn)
            
            if df.empty:
                self.logger.warning(f"Table {table_name} is empty, skipping backup")
                return True
            
            # Convert to Parquet with compression
            parquet_file = backup_path / f"{table_name}.parquet"
            
            # Ensure proper data types
            df = self._optimize_dataframe_types(df)
            
            # Write to Parquet with compression
            df.to_parquet(
                parquet_file,
                engine='pyarrow',
                compression=self.config.compression,
                index=False
            )
            
            self.logger.debug(f"Backed up table {table_name} to {parquet_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to backup table {table_name}: {e}")
            return False
    
    def _optimize_dataframe_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Optimize DataFrame data types for better compression."""
        for col in df.columns:
            if df[col].dtype == 'object':
                # Try to convert to numeric if possible
                try:
                    df[col] = pd.to_numeric(df[col], downcast='integer')
                except (ValueError, TypeError):
                    # Keep as string if conversion fails
                    df[col] = df[col].astype('string')
            elif df[col].dtype == 'float64':
                # Downcast to float32 if possible
                df[col] = pd.to_numeric(df[col], downcast='float')
        
        return df
    
    def _get_database_stats(self) -> Dict[str, int]:
        """Get record counts for all tables."""
        stats = {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                for table in self.config.tables_to_backup:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    stats[table] = count
        except Exception as e:
            self.logger.error(f"Failed to get database stats: {e}")
        
        return stats
    
    def _calculate_backup_size(self, backup_path: Path) -> int:
        """Calculate total size of backup directory."""
        total_size = 0
        for file_path in backup_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    def _calculate_compression_ratio(self, backup_size: int, db_stats: Dict[str, int]) -> float:
        """Calculate compression ratio compared to original database size."""
        try:
            db_size = self.db_path.stat().st_size
            if db_size > 0:
                return backup_size / db_size
        except Exception:
            pass
        return 1.0
    
    def _calculate_backup_checksum(self, backup_path: Path) -> str:
        """Calculate SHA256 checksum of backup directory."""
        hasher = hashlib.sha256()
        
        # Sort files for consistent checksum
        for file_path in sorted(backup_path.rglob('*')):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(4096), b""):
                        hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def _save_backup_metadata(self, backup_path: Path, metadata: BackupMetadata):
        """Save backup metadata to JSON file."""
        metadata_file = backup_path / 'metadata.json'
        metadata_dict = {
            'backup_id': metadata.backup_id,
            'timestamp': metadata.timestamp.isoformat(),
            'tables_backed_up': metadata.tables_backed_up,
            'total_records': metadata.total_records,
            'backup_size_bytes': metadata.backup_size_bytes,
            'compression_ratio': metadata.compression_ratio,
            'checksum': metadata.checksum,
            'status': metadata.status,
            'error_message': metadata.error_message
        }
        
        with open(metadata_file, 'w') as f:
            json.dump(metadata_dict, f, indent=2)
    
    async def _verify_backup_integrity(self, backup_path: Path, metadata: BackupMetadata) -> bool:
        """
        Verify backup integrity by checking file existence and checksums.
        
        Args:
            backup_path: Path to backup directory
            metadata: Backup metadata
            
        Returns:
            True if integrity check passes, False otherwise
        """
        try:
            # Check if all expected files exist
            for table_name in metadata.tables_backed_up:
                parquet_file = backup_path / f"{table_name}.parquet"
                if not parquet_file.exists():
                    self.logger.error(f"Missing backup file: {parquet_file}")
                    return False
                
                # Verify Parquet file can be read
                try:
                    df = pd.read_parquet(parquet_file)
                    if df.empty and metadata.total_records > 0:
                        self.logger.error(f"Backup file {parquet_file} is empty but should have data")
                        return False
                except Exception as e:
                    self.logger.error(f"Cannot read backup file {parquet_file}: {e}")
                    return False
            
            # Verify checksum
            current_checksum = self._calculate_backup_checksum(backup_path)
            if current_checksum != metadata.checksum:
                self.logger.error(f"Checksum mismatch for backup {metadata.backup_id}")
                return False
            
            self.logger.info(f"Backup integrity verification passed for {metadata.backup_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup integrity verification failed: {e}")
            return False
    
    async def restore_backup(self, backup_id: str, target_db_path: Optional[str] = None) -> bool:
        """
        Restore data from a backup.
        
        Args:
            backup_id: ID of the backup to restore
            target_db_path: Optional target database path (defaults to current db_path)
            
        Returns:
            True if restoration successful, False otherwise
        """
        if target_db_path is None:
            target_db_path = self.db_path
        
        self.logger.info(f"Restoring backup {backup_id} to {target_db_path}")
        
        try:
            backup_path = self.backup_dir / backup_id
            
            if not backup_path.exists():
                self.logger.error(f"Backup directory not found: {backup_path}")
                return False
            
            # Load backup metadata
            metadata_file = backup_path / 'metadata.json'
            if not metadata_file.exists():
                self.logger.error(f"Backup metadata not found: {metadata_file}")
                return False
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Verify backup integrity before restoration
            if not await self._verify_backup_integrity(backup_path, BackupMetadata(**metadata)):
                self.logger.error(f"Backup integrity check failed for {backup_id}")
                return False
            
            # Create target database if it doesn't exist
            target_db = Path(target_db_path)
            target_db.parent.mkdir(parents=True, exist_ok=True)
            
            # Restore each table
            with sqlite3.connect(target_db) as conn:
                cursor = conn.cursor()
                
                for table_name in metadata['tables_backed_up']:
                    parquet_file = backup_path / f"{table_name}.parquet"
                    
                    if not parquet_file.exists():
                        self.logger.warning(f"Backup file not found: {parquet_file}")
                        continue
                    
                    # Read Parquet data
                    df = pd.read_parquet(parquet_file)
                    
                    if df.empty:
                        self.logger.warning(f"Table {table_name} is empty in backup")
                        continue
                    
                    # Drop existing table if it exists
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                    
                    # Create table and insert data
                    df.to_sql(table_name, conn, if_exists='replace', index=False)
                    
                    self.logger.info(f"Restored table {table_name}: {len(df)} records")
            
            self.logger.info(f"Backup restoration completed: {backup_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup restoration failed: {e}")
            return False
    
    async def cleanup_old_backups(self):
        """Clean up old backups according to retention policy."""
        self.logger.info("Starting backup cleanup")
        
        try:
            current_time = datetime.now()
            cleaned_count = 0
            
            # Get all backup directories
            backup_dirs = [d for d in self.backup_dir.iterdir() if d.is_dir()]
            
            for backup_dir in backup_dirs:
                try:
                    # Load backup metadata
                    metadata_file = backup_dir / 'metadata.json'
                    if not metadata_file.exists():
                        self.logger.warning(f"No metadata found for {backup_dir}, skipping")
                        continue
                    
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    backup_time = datetime.fromisoformat(metadata['timestamp'])
                    age_days = (current_time - backup_time).days
                    
                    # Apply retention policy
                    should_delete = False
                    
                    if age_days > self.config.retention_years * 365:
                        should_delete = True
                    elif age_days > self.config.retention_months * 30:
                        # Keep only monthly backups
                        if backup_time.day != 1:  # Not first day of month
                            should_delete = True
                    elif age_days > self.config.retention_weeks * 7:
                        # Keep only weekly backups
                        if backup_time.weekday() != 0:  # Not Monday
                            should_delete = True
                    elif age_days > self.config.retention_days:
                        # Keep only daily backups
                        if backup_time.hour != 2:  # Not 2 AM backup
                            should_delete = True
                    
                    if should_delete:
                        shutil.rmtree(backup_dir)
                        cleaned_count += 1
                        self.logger.info(f"Deleted old backup: {backup_dir.name}")
                
                except Exception as e:
                    self.logger.error(f"Error processing backup {backup_dir}: {e}")
            
            self.logger.info(f"Backup cleanup completed: {cleaned_count} backups removed")
            
        except Exception as e:
            self.logger.error(f"Backup cleanup failed: {e}")
    
    def get_backup_status(self) -> Dict[str, Any]:
        """Get current backup status and statistics."""
        try:
            # Get backup directory size
            total_size = sum(f.stat().st_size for f in self.backup_dir.rglob('*') if f.is_file())
            
            # Count backups
            backup_dirs = [d for d in self.backup_dir.iterdir() if d.is_dir()]
            backup_count = len(backup_dirs)
            
            # Get latest backup info
            latest_backup = None
            if backup_dirs:
                latest_backup_dir = max(backup_dirs, key=lambda x: x.stat().st_mtime)
                metadata_file = latest_backup_dir / 'metadata.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        latest_backup = json.load(f)
            
            return {
                'backup_directory': str(self.backup_dir),
                'total_backups': backup_count,
                'total_size_mb': total_size / (1024 * 1024),
                'latest_backup': latest_backup,
                'config': {
                    'enabled': self.config.enabled,
                    'retention_days': self.config.retention_days,
                    'compression': self.config.compression,
                    'backup_time': self.config.backup_time
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get backup status: {e}")
            return {'error': str(e)}
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups with metadata."""
        backups = []
        
        try:
            backup_dirs = [d for d in self.backup_dir.iterdir() if d.is_dir()]
            
            for backup_dir in backup_dirs:
                metadata_file = backup_dir / 'metadata.json'
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    backups.append(metadata)
                else:
                    # Backup without metadata
                    backups.append({
                        'backup_id': backup_dir.name,
                        'timestamp': datetime.fromtimestamp(backup_dir.stat().st_mtime).isoformat(),
                        'status': 'unknown',
                        'tables_backed_up': [],
                        'total_records': 0,
                        'backup_size_bytes': 0
                    })
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
        except Exception as e:
            self.logger.error(f"Failed to list backups: {e}")
        
        return backups


class BackupScheduler:
    """Scheduler for automated backup operations."""
    
    def __init__(self, backup_manager: BackupManager):
        self.backup_manager = backup_manager
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start_scheduler(self):
        """Start the backup scheduler."""
        if self._running:
            self.logger.warning("Backup scheduler is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        self.logger.info("Backup scheduler started")
    
    async def stop_scheduler(self):
        """Stop the backup scheduler."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Backup scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop."""
        while self._running:
            try:
                # Check if it's time for backup
                if self._should_run_backup():
                    self.logger.info("Starting scheduled backup")
                    await self.backup_manager.create_backup()
                    
                    # Run cleanup after backup
                    await self.backup_manager.cleanup_old_backups()
                
                # Wait until next check (every hour)
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in backup scheduler: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retry
    
    def _should_run_backup(self) -> bool:
        """Check if backup should run based on configured time."""
        if not self.backup_manager.config.enabled:
            return False
        
        current_time = datetime.now()
        backup_hour, backup_minute = map(int, self.backup_manager.config.backup_time.split(':'))
        
        # Check if current time matches backup time (within 1 hour tolerance)
        if (current_time.hour == backup_hour and 
            current_time.minute >= backup_minute and 
            current_time.minute < backup_minute + 60):
            return True
        
        return False


# Factory function for creating backup manager
def create_backup_manager(config_path: str, db_path: str) -> BackupManager:
    """Create a new backup manager instance."""
    return BackupManager(config_path, db_path)


# Factory function for creating backup scheduler
def create_backup_scheduler(backup_manager: BackupManager) -> BackupScheduler:
    """Create a new backup scheduler instance."""
    return BackupScheduler(backup_manager)
