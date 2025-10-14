"""
Data models for the retention system.

This module contains all the data classes and enums used by the retention system.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class DataPriority(Enum):
    """Priority levels for data types."""
    CRITICAL = "critical"
    IMPORTANT = "important"
    OPERATIONAL = "operational"


@dataclass
class RetentionPolicy:
    """Configuration for data retention policy."""
    enabled: bool
    retention_days: int
    retention_weeks: int
    retention_months: int
    retention_years: int
    priority: DataPriority
    description: str


@dataclass
class CleanupOperation:
    """Represents a single cleanup operation."""
    operation_id: str
    timestamp: datetime
    data_type: str
    records_processed: int
    records_deleted: int
    storage_freed_bytes: int
    status: str  # 'success', 'failed', 'partial'
    duration_seconds: float
    error_message: Optional[str] = None


@dataclass
class StorageStats:
    """Storage statistics for the database."""
    total_size_bytes: int
    data_type_breakdown: Dict[str, int]
    record_counts: Dict[str, int]
    last_cleanup_date: Optional[datetime] = None


@dataclass
class RetentionConfig:
    """Configuration for retention operations."""
    global_settings: Dict[str, Any]
    scheduler_settings: Dict[str, Any]
    retention_policies: Dict[str, RetentionPolicy]
    cleanup_settings: Dict[str, Any]
    storage_monitoring: Dict[str, Any]
    data_integrity: Dict[str, Any]
    notifications: Dict[str, Any]
    compliance: Dict[str, Any]
