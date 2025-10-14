"""
Storage monitoring and reporting for the retention system.

This module handles storage space monitoring, usage reporting, alerts, and trend analysis.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import statistics

try:
    from .retention_models import StorageStats
except ImportError:
    from retention_models import StorageStats

logger = logging.getLogger(__name__)


class StorageMonitor:
    """Monitors storage usage and generates reports."""
    
    def __init__(self, db_path: str, logs_dir: str = "logs/retention"):
        self.db_path = Path(db_path)
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Storage history for trend analysis
        self.storage_history_file = self.logs_dir / "storage_history.json"
        self._load_storage_history()
    
    def _load_storage_history(self):
        """Load storage history from file."""
        try:
            if self.storage_history_file.exists():
                with open(self.storage_history_file, 'r') as f:
                    self.storage_history = json.load(f)
            else:
                self.storage_history = []
        except Exception as e:
            logger.error(f"Failed to load storage history: {e}")
            self.storage_history = []
    
    def _save_storage_history(self):
        """Save storage history to file."""
        try:
            with open(self.storage_history_file, 'w') as f:
                json.dump(self.storage_history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save storage history: {e}")
    
    async def get_current_storage_stats(self) -> StorageStats:
        """Get current storage statistics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get database size
                cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
                total_size = cursor.fetchone()[0]
                
                # Get table information
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                data_type_breakdown = {}
                record_counts = {}
                
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    record_counts[table] = count
                    
                    # Get actual table size
                    cursor.execute(f"SELECT COUNT(*) * 100 FROM {table}")  # Rough estimate
                    data_type_breakdown[table] = count * 100
                
                # Get last cleanup date from logs
                last_cleanup_date = self._get_last_cleanup_date()
                
                return StorageStats(
                    total_size_bytes=total_size,
                    data_type_breakdown=data_type_breakdown,
                    record_counts=record_counts,
                    last_cleanup_date=last_cleanup_date
                )
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return StorageStats(0, {}, {})
    
    def _get_last_cleanup_date(self) -> Optional[datetime]:
        """Get the last cleanup date from logs."""
        try:
            # Look for the most recent cleanup log
            log_files = list(self.logs_dir.glob("cleanup_operations_*.jsonl"))
            if not log_files:
                return None
            
            # Get the most recent log file
            latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
            
            # Read the last entry
            with open(latest_log, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    return datetime.fromisoformat(last_entry['timestamp'])
            
            return None
        except Exception as e:
            logger.error(f"Failed to get last cleanup date: {e}")
            return None
    
    async def record_storage_snapshot(self):
        """Record current storage state for trend analysis."""
        try:
            stats = await self.get_current_storage_stats()
            
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "total_size_bytes": stats.total_size_bytes,
                "total_size_mb": round(stats.total_size_bytes / 1024 / 1024, 2),
                "data_type_breakdown": stats.data_type_breakdown,
                "record_counts": stats.record_counts,
                "last_cleanup_date": stats.last_cleanup_date.isoformat() if stats.last_cleanup_date else None
            }
            
            self.storage_history.append(snapshot)
            
            # Keep only last 30 days of history
            cutoff_date = datetime.now() - timedelta(days=30)
            self.storage_history = [
                entry for entry in self.storage_history
                if datetime.fromisoformat(entry['timestamp']) > cutoff_date
            ]
            
            self._save_storage_history()
            logger.debug(f"Storage snapshot recorded: {snapshot['total_size_mb']} MB")
            
        except Exception as e:
            logger.error(f"Failed to record storage snapshot: {e}")
    
    async def analyze_storage_trends(self, days: int = 7) -> Dict[str, Any]:
        """Analyze storage usage trends over specified period."""
        try:
            if not self.storage_history:
                return {"error": "No storage history available"}
            
            # Filter data for the specified period
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_data = [
                entry for entry in self.storage_history
                if datetime.fromisoformat(entry['timestamp']) > cutoff_date
            ]
            
            if len(recent_data) < 2:
                return {"error": "Insufficient data for trend analysis"}
            
            # Extract size data
            sizes = [entry['total_size_bytes'] for entry in recent_data]
            timestamps = [datetime.fromisoformat(entry['timestamp']) for entry in recent_data]
            
            # Calculate trends
            size_trend = self._calculate_trend(sizes)
            growth_rate = self._calculate_growth_rate(sizes)
            predicted_size = self._predict_future_size(sizes, days=7)
            
            # Analyze data type trends
            data_type_trends = self._analyze_data_type_trends(recent_data)
            
            return {
                "analysis_period_days": days,
                "data_points": len(recent_data),
                "current_size_mb": round(sizes[-1] / 1024 / 1024, 2),
                "size_trend": size_trend,
                "growth_rate_mb_per_day": round(growth_rate / 1024 / 1024, 2),
                "predicted_size_mb_7_days": round(predicted_size / 1024 / 1024, 2),
                "data_type_trends": data_type_trends,
                "recommendations": self._generate_storage_recommendations(sizes, growth_rate, data_type_trends)
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze storage trends: {e}")
            return {"error": str(e)}
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return "insufficient_data"
        
        # Simple linear trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]
        
        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)
        
        if second_avg > first_avg * 1.05:  # 5% increase
            return "increasing"
        elif second_avg < first_avg * 0.95:  # 5% decrease
            return "decreasing"
        else:
            return "stable"
    
    def _calculate_growth_rate(self, sizes: List[float]) -> float:
        """Calculate daily growth rate in bytes."""
        if len(sizes) < 2:
            return 0
        
        # Calculate average daily change
        total_change = sizes[-1] - sizes[0]
        days = len(sizes) - 1
        return total_change / days if days > 0 else 0
    
    def _predict_future_size(self, sizes: List[float], days: int = 7) -> float:
        """Predict future storage size based on current trend."""
        if len(sizes) < 2:
            return sizes[-1] if sizes else 0
        
        growth_rate = self._calculate_growth_rate(sizes)
        return sizes[-1] + (growth_rate * days)
    
    def _analyze_data_type_trends(self, recent_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze trends for each data type."""
        data_type_trends = {}
        
        # Get all data types from the most recent entry
        if not recent_data:
            return data_type_trends
        
        data_types = recent_data[-1].get('data_type_breakdown', {}).keys()
        
        for data_type in data_types:
            values = []
            for entry in recent_data:
                if data_type in entry.get('data_type_breakdown', {}):
                    values.append(entry['data_type_breakdown'][data_type])
            
            if len(values) >= 2:
                trend = self._calculate_trend(values)
                growth_rate = self._calculate_growth_rate(values)
                
                data_type_trends[data_type] = {
                    "trend": trend,
                    "growth_rate_bytes_per_day": growth_rate,
                    "current_size_bytes": values[-1],
                    "current_size_mb": round(values[-1] / 1024 / 1024, 2)
                }
        
        return data_type_trends
    
    def _generate_storage_recommendations(self, sizes: List[float], growth_rate: float, data_type_trends: Dict[str, Any]) -> List[str]:
        """Generate storage recommendations based on analysis."""
        recommendations = []
        
        current_size_mb = sizes[-1] / 1024 / 1024 if sizes else 0
        growth_rate_mb_per_day = growth_rate / 1024 / 1024
        
        # Check for high growth rate
        if growth_rate_mb_per_day > 100:  # More than 100MB per day
            recommendations.append("🚨 High storage growth rate detected - consider more aggressive retention policies")
        
        # Check for large database size
        if current_size_mb > 1000:  # More than 1GB
            recommendations.append("💾 Large database size detected - review retention periods and consider archiving")
        
        # Check for specific data type issues
        for data_type, trends in data_type_trends.items():
            if trends.get('trend') == 'increasing' and trends.get('growth_rate_bytes_per_day', 0) > 1024 * 1024:  # 1MB per day
                recommendations.append(f"📈 High growth in {data_type} - consider shorter retention period")
        
        # Check for cleanup effectiveness
        if len(sizes) >= 3:
            recent_sizes = sizes[-3:]
            if all(recent_sizes[i] >= recent_sizes[i-1] for i in range(1, len(recent_sizes))):
                recommendations.append("🧹 Storage not decreasing - check if cleanup operations are running effectively")
        
        if not recommendations:
            recommendations.append("✅ Storage usage appears normal - no immediate action required")
        
        return recommendations
    
    async def generate_storage_report(self, include_trends: bool = True) -> Dict[str, Any]:
        """Generate comprehensive storage report."""
        try:
            # Get current stats
            current_stats = await self.get_current_storage_stats()
            
            # Calculate basic metrics
            total_size_mb = current_stats.total_size_bytes / 1024 / 1024
            data_type_sizes = {
                dt: size / 1024 / 1024 for dt, size in current_stats.data_type_breakdown.items()
            }
            
            report = {
                "report_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "report_type": "storage_analysis",
                    "database_path": str(self.db_path),
                    "report_version": "1.0.0"
                },
                "current_storage": {
                    "total_size_bytes": current_stats.total_size_bytes,
                    "total_size_mb": round(total_size_mb, 2),
                    "total_size_gb": round(total_size_mb / 1024, 2),
                    "data_type_breakdown": data_type_sizes,
                    "record_counts": current_stats.record_counts,
                    "last_cleanup_date": current_stats.last_cleanup_date.isoformat() if current_stats.last_cleanup_date else None
                },
                "storage_health": {
                    "status": self._assess_storage_health(total_size_mb),
                    "recommendations": self._get_basic_recommendations(total_size_mb, data_type_sizes)
                }
            }
            
            # Add trend analysis if requested
            if include_trends:
                trend_analysis = await self.analyze_storage_trends()
                report["trend_analysis"] = trend_analysis
            
            # Save report
            await self._save_storage_report(report)
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate storage report: {e}")
            return {"error": str(e)}
    
    def _assess_storage_health(self, total_size_mb: float) -> str:
        """Assess overall storage health."""
        if total_size_mb > 5000:  # 5GB
            return "critical"
        elif total_size_mb > 1000:  # 1GB
            return "warning"
        elif total_size_mb > 500:  # 500MB
            return "caution"
        else:
            return "healthy"
    
    def _get_basic_recommendations(self, total_size_mb: float, data_type_sizes: Dict[str, float]) -> List[str]:
        """Get basic storage recommendations."""
        recommendations = []
        
        if total_size_mb > 1000:
            recommendations.append("💾 Database size exceeds 1GB - consider running cleanup operations")
        
        # Find largest data types
        largest_types = sorted(data_type_sizes.items(), key=lambda x: x[1], reverse=True)[:3]
        for data_type, size_mb in largest_types:
            if size_mb > 100:  # 100MB
                recommendations.append(f"📊 {data_type} is using {size_mb:.1f}MB - review retention policy")
        
        if not recommendations:
            recommendations.append("✅ Storage usage is within normal limits")
        
        return recommendations
    
    async def _save_storage_report(self, report: Dict[str, Any]):
        """Save storage report to file."""
        try:
            reports_dir = self.logs_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = reports_dir / f"storage_report_{timestamp}.json"
            
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Storage report saved: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to save storage report: {e}")
    
    async def check_storage_thresholds(self, warning_threshold_mb: float = 1000, critical_threshold_mb: float = 5000) -> Dict[str, Any]:
        """Check storage against configured thresholds."""
        try:
            stats = await self.get_current_storage_stats()
            current_size_mb = stats.total_size_bytes / 1024 / 1024
            
            status = "normal"
            alert_level = None
            message = None
            
            if current_size_mb >= critical_threshold_mb:
                status = "critical"
                alert_level = "critical"
                alert_level = "critical"
                message = f"🚨 CRITICAL: Database size ({current_size_mb:.1f}MB) exceeds critical threshold ({critical_threshold_mb}MB)"
            elif current_size_mb >= warning_threshold_mb:
                status = "warning"
                alert_level = "warning"
                message = f"⚠️ WARNING: Database size ({current_size_mb:.1f}MB) exceeds warning threshold ({warning_threshold_mb}MB)"
            else:
                message = f"✅ Database size ({current_size_mb:.1f}MB) is within normal limits"
            
            return {
                "status": status,
                "alert_level": alert_level,
                "current_size_mb": round(current_size_mb, 2),
                "warning_threshold_mb": warning_threshold_mb,
                "critical_threshold_mb": critical_threshold_mb,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to check storage thresholds: {e}")
            return {"error": str(e)}
