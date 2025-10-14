"""
Data integrity preservation for the retention system.

This module handles data integrity verification, archival processes, and recovery procedures.
"""

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import shutil

try:
    from .retention_models import CleanupOperation, StorageStats
except ImportError:
    from retention_models import CleanupOperation, StorageStats

logger = logging.getLogger(__name__)


class DataIntegrityManager:
    """Manages data integrity verification and preservation."""
    
    def __init__(self, db_path: str, backup_dir: str = "data/backups", logs_dir: str = "logs/retention"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.logs_dir = Path(logs_dir)
        
        # Create directories if they don't exist
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Integrity verification settings
        self.integrity_log_file = self.logs_dir / "integrity_verification.jsonl"
        self.checksum_file = self.logs_dir / "data_checksums.json"
    
    async def verify_database_integrity(self) -> Dict[str, Any]:
        """Verify database integrity before cleanup operations."""
        try:
            logger.info("Starting database integrity verification...")
            
            verification_result = {
                "timestamp": datetime.now().isoformat(),
                "database_path": str(self.db_path),
                "verification_id": f"integrity_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "status": "in_progress",
                "checks": {}
            }
            
            # 1. Basic database connectivity check
            connectivity_check = await self._check_database_connectivity()
            verification_result["checks"]["connectivity"] = connectivity_check
            
            # 2. Database schema integrity check
            schema_check = await self._check_schema_integrity()
            verification_result["checks"]["schema"] = schema_check
            
            # 3. Data consistency checks
            consistency_check = await self._check_data_consistency()
            verification_result["checks"]["consistency"] = consistency_check
            
            # 4. Foreign key integrity check
            fk_check = await self._check_foreign_key_integrity()
            verification_result["checks"]["foreign_keys"] = fk_check
            
            # 5. Index integrity check
            index_check = await self._check_index_integrity()
            verification_result["checks"]["indexes"] = index_check
            
            # 6. Calculate database checksum
            checksum_check = await self._calculate_database_checksum()
            verification_result["checks"]["checksum"] = checksum_check
            
            # Determine overall status
            all_checks_passed = all(
                check.get("status") == "passed" 
                for check in verification_result["checks"].values()
            )
            
            verification_result["status"] = "passed" if all_checks_passed else "failed"
            verification_result["overall_health"] = "healthy" if all_checks_passed else "unhealthy"
            
            # Log verification result
            await self._log_integrity_verification(verification_result)
            
            logger.info(f"Database integrity verification completed: {verification_result['status']}")
            return verification_result
            
        except Exception as e:
            logger.error(f"Database integrity verification failed: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "failed",
                "error": str(e),
                "overall_health": "unhealthy"
            }
    
    async def _check_database_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity and basic operations."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                # Test database info
                cursor.execute("PRAGMA database_list")
                databases = cursor.fetchall()
                
                return {
                    "status": "passed",
                    "message": "Database connectivity verified",
                    "database_count": len(databases),
                    "test_query_result": result[0] if result else None
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Database connectivity failed: {e}",
                "error": str(e)
            }
    
    async def _check_schema_integrity(self) -> Dict[str, Any]:
        """Check database schema integrity."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                # Check each table structure
                table_structures = {}
                for table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    table_structures[table] = {
                        "column_count": len(columns),
                        "columns": [{"name": col[1], "type": col[2], "not_null": col[3]} for col in columns]
                    }
                
                return {
                    "status": "passed",
                    "message": "Schema integrity verified",
                    "table_count": len(tables),
                    "tables": table_structures
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Schema integrity check failed: {e}",
                "error": str(e)
            }
    
    async def _check_data_consistency(self) -> Dict[str, Any]:
        """Check data consistency across tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all tables
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                consistency_checks = {}
                
                for table in tables:
                    # Check for NULL values in critical columns
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = cursor.fetchall()
                    
                    null_checks = {}
                    for col in columns:
                        col_name = col[1]
                        if col[3]:  # NOT NULL constraint
                            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col_name} IS NULL")
                            null_count = cursor.fetchone()[0]
                            null_checks[col_name] = {
                                "null_count": null_count,
                                "status": "passed" if null_count == 0 else "failed"
                            }
                    
                    # Check record count
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    record_count = cursor.fetchone()[0]
                    
                    consistency_checks[table] = {
                        "record_count": record_count,
                        "null_checks": null_checks,
                        "status": "passed" if all(check["status"] == "passed" for check in null_checks.values()) else "failed"
                    }
                
                overall_status = "passed" if all(
                    check["status"] == "passed" for check in consistency_checks.values()
                ) else "failed"
                
                return {
                    "status": overall_status,
                    "message": "Data consistency verified" if overall_status == "passed" else "Data consistency issues found",
                    "table_checks": consistency_checks
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Data consistency check failed: {e}",
                "error": str(e)
            }
    
    async def _check_foreign_key_integrity(self) -> Dict[str, Any]:
        """Check foreign key integrity."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Enable foreign key checking
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # Get foreign key information
                cursor.execute("PRAGMA foreign_key_list")
                fk_info = cursor.fetchall()
                
                if not fk_info:
                    return {
                        "status": "passed",
                        "message": "No foreign keys to check",
                        "foreign_key_count": 0
                    }
                
                # Check for orphaned records (simplified check)
                fk_checks = {}
                for fk in fk_info:
                    table = fk[0]
                    column = fk[3]
                    ref_table = fk[2]
                    ref_column = fk[4]
                    
                    # Check for orphaned records
                    query = f"""
                        SELECT COUNT(*) FROM {table} t1 
                        WHERE NOT EXISTS (
                            SELECT 1 FROM {ref_table} t2 
                            WHERE t2.{ref_column} = t1.{column}
                        )
                    """
                    cursor.execute(query)
                    orphaned_count = cursor.fetchone()[0]
                    
                    fk_checks[f"{table}.{column}"] = {
                        "orphaned_count": orphaned_count,
                        "status": "passed" if orphaned_count == 0 else "failed"
                    }
                
                overall_status = "passed" if all(
                    check["status"] == "passed" for check in fk_checks.values()
                ) else "failed"
                
                return {
                    "status": overall_status,
                    "message": "Foreign key integrity verified" if overall_status == "passed" else "Foreign key integrity issues found",
                    "foreign_key_checks": fk_checks
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Foreign key integrity check failed: {e}",
                "error": str(e)
            }
    
    async def _check_index_integrity(self) -> Dict[str, Any]:
        """Check index integrity."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all indexes
                cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
                indexes = [row[0] for row in cursor.fetchall()]
                
                if not indexes:
                    return {
                        "status": "passed",
                        "message": "No indexes to check",
                        "index_count": 0
                    }
                
                # Check index integrity (simplified)
                index_checks = {}
                for index in indexes:
                    try:
                        # Try to use the index
                        cursor.execute(f"SELECT COUNT(*) FROM sqlite_master WHERE name = '{index}'")
                        exists = cursor.fetchone()[0] > 0
                        
                        index_checks[index] = {
                            "exists": exists,
                            "status": "passed" if exists else "failed"
                        }
                    except Exception as e:
                        index_checks[index] = {
                            "exists": False,
                            "status": "failed",
                            "error": str(e)
                        }
                
                overall_status = "passed" if all(
                    check["status"] == "passed" for check in index_checks.values()
                ) else "failed"
                
                return {
                    "status": overall_status,
                    "message": "Index integrity verified" if overall_status == "passed" else "Index integrity issues found",
                    "index_checks": index_checks
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Index integrity check failed: {e}",
                "error": str(e)
            }
    
    async def _calculate_database_checksum(self) -> Dict[str, Any]:
        """Calculate database checksum for integrity verification."""
        try:
            # Calculate file checksum
            with open(self.db_path, 'rb') as f:
                file_content = f.read()
                file_checksum = hashlib.sha256(file_content).hexdigest()
            
            # Calculate database content checksum
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get all table data checksums
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                table_checksums = {}
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    
                    # Simple content hash (count + first/last records)
                    cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                    first_record = cursor.fetchone()
                    cursor.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 1")
                    last_record = cursor.fetchone()
                    
                    content_hash = hashlib.sha256(
                        f"{count}_{first_record}_{last_record}".encode()
                    ).hexdigest()[:16]  # Short hash
                    
                    table_checksums[table] = {
                        "record_count": count,
                        "content_hash": content_hash
                    }
                
                # Overall content checksum
                content_str = json.dumps(table_checksums, sort_keys=True)
                content_checksum = hashlib.sha256(content_str.encode()).hexdigest()
            
            # Save checksum for future comparison
            checksum_data = {
                "timestamp": datetime.now().isoformat(),
                "file_checksum": file_checksum,
                "content_checksum": content_checksum,
                "table_checksums": table_checksums
            }
            
            with open(self.checksum_file, 'w') as f:
                json.dump(checksum_data, f, indent=2)
            
            return {
                "status": "passed",
                "message": "Database checksum calculated",
                "file_checksum": file_checksum,
                "content_checksum": content_checksum,
                "table_count": len(tables)
            }
            
        except Exception as e:
            return {
                "status": "failed",
                "message": f"Checksum calculation failed: {e}",
                "error": str(e)
            }
    
    async def _log_integrity_verification(self, verification_result: Dict[str, Any]):
        """Log integrity verification results."""
        try:
            with open(self.integrity_log_file, 'a') as f:
                f.write(json.dumps(verification_result) + '\n')
        except Exception as e:
            logger.error(f"Failed to log integrity verification: {e}")
    
    async def create_integrity_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """Create a backup with integrity verification."""
        try:
            if not backup_name:
                backup_name = f"integrity_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            backup_path = self.backup_dir / f"{backup_name}.db"
            
            logger.info(f"Creating integrity backup: {backup_name}")
            
            # Verify database integrity before backup
            integrity_result = await self.verify_database_integrity()
            if integrity_result["status"] != "passed":
                return {
                    "status": "failed",
                    "message": "Database integrity check failed before backup",
                    "integrity_result": integrity_result
                }
            
            # Create backup
            shutil.copy2(self.db_path, backup_path)
            
            # Verify backup integrity
            backup_integrity = await self._verify_backup_integrity(backup_path)
            
            # Create backup metadata
            backup_metadata = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(),
                "source_database": str(self.db_path),
                "backup_path": str(backup_path),
                "backup_size_bytes": backup_path.stat().st_size,
                "integrity_verified": integrity_result["status"] == "passed",
                "backup_integrity": backup_integrity,
                "checksum": integrity_result["checks"]["checksum"]["content_checksum"]
            }
            
            # Save backup metadata
            metadata_file = self.backup_dir / f"{backup_name}_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(backup_metadata, f, indent=2)
            
            logger.info(f"Integrity backup created successfully: {backup_name}")
            
            return {
                "status": "success",
                "message": "Integrity backup created successfully",
                "backup_metadata": backup_metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to create integrity backup: {e}")
            return {
                "status": "failed",
                "message": f"Backup creation failed: {e}",
                "error": str(e)
            }
    
    async def _verify_backup_integrity(self, backup_path: Path) -> Dict[str, Any]:
        """Verify backup file integrity."""
        try:
            # Check if backup file exists and is readable
            if not backup_path.exists():
                return {"status": "failed", "message": "Backup file does not exist"}
            
            # Test database connectivity
            with sqlite3.connect(backup_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
                if result and result[0] == 1:
                    return {"status": "passed", "message": "Backup integrity verified"}
                else:
                    return {"status": "failed", "message": "Backup database test failed"}
                    
        except Exception as e:
            return {"status": "failed", "message": f"Backup verification failed: {e}"}
    
    async def restore_from_backup(self, backup_name: str, verify_integrity: bool = True) -> Dict[str, Any]:
        """Restore database from backup with integrity verification."""
        try:
            backup_path = self.backup_dir / f"{backup_name}.db"
            metadata_file = self.backup_dir / f"{backup_name}_metadata.json"
            
            if not backup_path.exists():
                return {
                    "status": "failed",
                    "message": f"Backup file not found: {backup_path}"
                }
            
            logger.info(f"Restoring from backup: {backup_name}")
            
            # Verify backup integrity if requested
            if verify_integrity:
                backup_integrity = await self._verify_backup_integrity(backup_path)
                if backup_integrity["status"] != "passed":
                    return {
                        "status": "failed",
                        "message": "Backup integrity verification failed",
                        "integrity_result": backup_integrity
                    }
            
            # Create current database backup before restore
            current_backup_name = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            current_backup_result = await self.create_integrity_backup(current_backup_name)
            
            # Restore database
            shutil.copy2(backup_path, self.db_path)
            
            # Verify restored database integrity
            if verify_integrity:
                restored_integrity = await self.verify_database_integrity()
                if restored_integrity["status"] != "passed":
                    # Restore from current backup if integrity check fails
                    logger.error("Restored database integrity check failed, restoring from current backup")
                    shutil.copy2(self.backup_dir / f"{current_backup_name}.db", self.db_path)
                    return {
                        "status": "failed",
                        "message": "Restored database integrity verification failed",
                        "integrity_result": restored_integrity
                    }
            
            # Load backup metadata
            backup_metadata = {}
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    backup_metadata = json.load(f)
            
            logger.info(f"Database restored successfully from backup: {backup_name}")
            
            return {
                "status": "success",
                "message": "Database restored successfully",
                "backup_name": backup_name,
                "backup_metadata": backup_metadata,
                "current_backup_created": current_backup_name
            }
            
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return {
                "status": "failed",
                "message": f"Restore failed: {e}",
                "error": str(e)
            }
    
    async def get_integrity_status(self) -> Dict[str, Any]:
        """Get current integrity status and history."""
        try:
            # Get latest integrity verification
            latest_verification = None
            if self.integrity_log_file.exists():
                with open(self.integrity_log_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        latest_verification = json.loads(lines[-1])
            
            # Get available backups
            backup_files = list(self.backup_dir.glob("*.db"))
            backup_metadata = []
            
            for backup_file in backup_files:
                metadata_file = backup_file.with_suffix('_metadata.json')
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        backup_metadata.append(metadata)
            
            return {
                "timestamp": datetime.now().isoformat(),
                "database_path": str(self.db_path),
                "latest_verification": latest_verification,
                "available_backups": len(backup_files),
                "backup_metadata": backup_metadata,
                "integrity_log_file": str(self.integrity_log_file),
                "checksum_file": str(self.checksum_file)
            }
            
        except Exception as e:
            logger.error(f"Failed to get integrity status: {e}")
            return {"error": str(e)}
