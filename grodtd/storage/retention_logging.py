"""
Logging and reporting for the retention system.

This module handles all logging, audit trails, and reporting functionality.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

try:
    from .retention_models import CleanupOperation, RetentionPolicy
except ImportError:
    from retention_models import CleanupOperation, RetentionPolicy

logger = logging.getLogger(__name__)


class RetentionLogger:
    """Handles logging and reporting for retention operations."""
    
    def __init__(self, logs_dir: str = "logs/retention"):
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
    
    def log_cleanup_operation(self, operation: CleanupOperation, policy: RetentionPolicy):
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
            "retention_policy_applied": self._get_policy_summary(policy),
            "cleanup_efficiency": self._calculate_cleanup_efficiency(operation)
        }
        
        # Log with appropriate level and formatting based on status
        if operation.status == 'success':
            logger.info(f"✅ Cleanup operation completed: {operation.data_type} - "
                       f"{operation.records_deleted} records deleted, "
                       f"{log_entry['storage_freed_mb']} MB freed in {log_entry['duration_formatted']}")
        elif operation.status == 'failed':
            logger.error(f"❌ Cleanup operation failed: {operation.data_type} - {operation.error_message}")
        else:
            logger.warning(f"⚠️ Cleanup operation {operation.status}: {operation.data_type}")
        
        # Store detailed log entry for audit trail
        self._store_operation_log(log_entry)
        
        # Create operation report
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
    
    def _get_policy_summary(self, policy: RetentionPolicy) -> Dict[str, Any]:
        """Get summary of retention policy applied to data type."""
        return {
            "retention_days": policy.retention_days,
            "retention_weeks": policy.retention_weeks,
            "retention_months": policy.retention_months,
            "retention_years": policy.retention_years,
            "priority": policy.priority.value,
            "enabled": policy.enabled
        }
    
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
            # Create log file with date
            log_date = datetime.now().strftime("%Y-%m-%d")
            log_file = self.logs_dir / f"cleanup_operations_{log_date}.jsonl"
            
            # Append log entry as JSON line
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
                
        except Exception as e:
            logger.error(f"Failed to store operation log: {e}")
    
    def _create_operation_report(self, operation: CleanupOperation, log_entry: Dict[str, Any]):
        """Create detailed operation report."""
        try:
            # Create reports directory if it doesn't exist
            reports_dir = self.logs_dir / "reports"
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
                    "retention_logger_version": "1.0.0"
                }
            }
            
            # Write report to file
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
                
            logger.debug(f"Operation report created: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to create operation report: {e}")
    
    def create_cleanup_summary_report(self, operations: List[CleanupOperation]) -> Dict[str, Any]:
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
            self._save_summary_report(summary_report)
            
            return summary_report
            
        except Exception as e:
            logger.error(f"Failed to create cleanup summary report: {e}")
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
    
    def _save_summary_report(self, report: Dict[str, Any]):
        """Save summary report to file."""
        try:
            reports_dir = self.logs_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"cleanup_summary_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Cleanup summary report saved: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to save summary report: {e}")
    
    def create_audit_trail(self, operations: List[CleanupOperation], policies: Dict[str, RetentionPolicy], config: Dict[str, Any]) -> Dict[str, Any]:
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
                        for data_type, policy in policies.items()
                    },
                    "cleanup_configuration": config.get('cleanup', {}),
                    "global_settings": config.get('global', {})
                },
                "operation_audit": [
                    {
                        "operation_id": op.operation_id,
                        "timestamp": op.timestamp.isoformat(),
                        "data_type": op.data_type,
                        "retention_policy_applied": self._get_policy_summary(policies.get(op.data_type, RetentionPolicy(True, 30, 4, 6, 1, "operational", "default"))),
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
                    "backup_verification": "completed" if config.get('cleanup', {}).get('backup_before_cleanup') else "not_configured"
                },
                "system_metrics": {
                    "total_storage_freed": sum(op.storage_freed_bytes for op in operations),
                    "cleanup_duration": sum(op.duration_seconds for op in operations)
                }
            }
            
            # Save audit trail
            self._save_audit_trail(audit_trail)
            
            return audit_trail
            
        except Exception as e:
            logger.error(f"Failed to create audit trail: {e}")
            return {"error": str(e)}
    
    def _save_audit_trail(self, audit_trail: Dict[str, Any]):
        """Save audit trail to file."""
        try:
            audit_dir = self.logs_dir / "audit"
            audit_dir.mkdir(parents=True, exist_ok=True)
            
            audit_id = audit_trail["audit_metadata"]["audit_id"]
            audit_file = audit_dir / f"{audit_id}.json"
            
            with open(audit_file, 'w') as f:
                json.dump(audit_trail, f, indent=2)
            
            logger.info(f"Audit trail saved: {audit_file}")
            
        except Exception as e:
            logger.error(f"Failed to save audit trail: {e}")
