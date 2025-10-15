"""
Performance monitoring module for GRODT trading system.

This module provides comprehensive performance monitoring capabilities including
system resource monitoring, application performance profiling, and performance
trend analysis.
"""

import asyncio
import psutil
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import structlog
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry

logger = structlog.get_logger(__name__)


@dataclass
class SystemMetrics:
    """System resource metrics."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_used_gb: float
    disk_free_gb: float
    network_sent_mb: float
    network_recv_mb: float


@dataclass
class ApplicationMetrics:
    """Application performance metrics."""
    timestamp: datetime
    response_time_ms: float
    throughput_rps: float
    active_connections: int
    error_rate_percent: float
    queue_size: int


@dataclass
class DatabaseMetrics:
    """Database performance metrics."""
    timestamp: datetime
    query_time_ms: float
    connection_count: int
    cache_hit_ratio: float
    slow_queries_count: int


@dataclass
class TradingMetrics:
    """Trading operation performance metrics."""
    timestamp: datetime
    order_processing_time_ms: float
    signal_generation_time_ms: float
    strategy_execution_time_ms: float
    trade_count: int


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    
    Monitors system resources, application performance, database operations,
    and trading-specific metrics with minimal overhead.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize performance monitor.
        
        Args:
            config: Configuration dictionary with monitoring settings
        """
        self.config = config or {}
        self.logger = structlog.get_logger(__name__)
        
        # Initialize Prometheus metrics
        self.registry = CollectorRegistry()
        self._setup_prometheus_metrics()
        
        # Performance tracking
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        
        # Historical data storage
        self.metrics_history: List[Dict[str, Any]] = []
        self.max_history_size = self.config.get('max_history_size', 1000)
        
        # Performance thresholds
        self.thresholds = {
            'cpu_percent': self.config.get('cpu_threshold', 80.0),
            'memory_percent': self.config.get('memory_threshold', 85.0),
            'disk_percent': self.config.get('disk_threshold', 90.0),
            'response_time_ms': self.config.get('response_time_threshold', 1000.0),
            'query_time_ms': self.config.get('query_time_threshold', 100.0)
        }
        
        self.logger.info("Performance monitor initialized", 
                        thresholds=self.thresholds)
    
    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics for performance monitoring."""
        # System metrics
        self.cpu_gauge = Gauge('system_cpu_percent', 'CPU usage percentage', registry=self.registry)
        self.memory_gauge = Gauge('system_memory_percent', 'Memory usage percentage', registry=self.registry)
        self.disk_gauge = Gauge('system_disk_percent', 'Disk usage percentage', registry=self.registry)
        
        # Application metrics
        self.response_time_histogram = Histogram(
            'application_response_time_seconds',
            'Application response time',
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0],
            registry=self.registry
        )
        self.throughput_counter = Counter('application_requests_total', 'Total requests', registry=self.registry)
        self.error_counter = Counter('application_errors_total', 'Total errors', registry=self.registry)
        
        # Database metrics
        self.query_time_histogram = Histogram(
            'database_query_time_seconds',
            'Database query time',
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )
        
        # Trading metrics
        self.order_processing_histogram = Histogram(
            'trading_order_processing_seconds',
            'Order processing time',
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
            registry=self.registry
        )
    
    async def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect current system resource metrics.
        
        Returns:
            SystemMetrics: Current system resource data
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_used_mb = memory.used / (1024 * 1024)
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_usage_percent = (disk.used / disk.total) * 100
            disk_used_gb = disk.used / (1024 * 1024 * 1024)
            disk_free_gb = disk.free / (1024 * 1024 * 1024)
            
            # Network metrics
            network = psutil.net_io_counters()
            network_sent_mb = network.bytes_sent / (1024 * 1024)
            network_recv_mb = network.bytes_recv / (1024 * 1024)
            
            metrics = SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_used_mb=memory_used_mb,
                memory_available_mb=memory_available_mb,
                disk_usage_percent=disk_usage_percent,
                disk_used_gb=disk_used_gb,
                disk_free_gb=disk_free_gb,
                network_sent_mb=network_sent_mb,
                network_recv_mb=network_recv_mb
            )
            
            # Update Prometheus metrics
            self.cpu_gauge.set(cpu_percent)
            self.memory_gauge.set(memory_percent)
            self.disk_gauge.set(disk_usage_percent)
            
            self.logger.debug("System metrics collected", 
                            cpu_percent=cpu_percent,
                            memory_percent=memory_percent,
                            disk_percent=disk_usage_percent)
            
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to collect system metrics", error=str(e))
            raise
    
    async def collect_application_metrics(self) -> ApplicationMetrics:
        """
        Collect current application performance metrics.
        
        Returns:
            ApplicationMetrics: Current application performance data
        """
        try:
            # Calculate uptime
            uptime_seconds = time.time() - self.start_time
            
            # Calculate throughput (requests per second)
            throughput_rps = self.request_count / uptime_seconds if uptime_seconds > 0 else 0
            
            # Calculate error rate
            error_rate_percent = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
            
            metrics = ApplicationMetrics(
                timestamp=datetime.now(),
                response_time_ms=0.0,  # Will be updated by request tracking
                throughput_rps=throughput_rps,
                active_connections=0,  # Will be implemented with connection tracking
                error_rate_percent=error_rate_percent,
                queue_size=0  # Will be implemented with queue tracking
            )
            
            self.logger.debug("Application metrics collected",
                            throughput_rps=throughput_rps,
                            error_rate_percent=error_rate_percent)
            
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to collect application metrics", error=str(e))
            raise
    
    async def collect_database_metrics(self) -> DatabaseMetrics:
        """
        Collect current database performance metrics.
        
        Returns:
            DatabaseMetrics: Current database performance data
        """
        try:
            # This would integrate with actual database monitoring
            # For now, return placeholder metrics
            metrics = DatabaseMetrics(
                timestamp=datetime.now(),
                query_time_ms=0.0,  # Will be updated by query tracking
                connection_count=0,  # Will be updated by connection monitoring
                cache_hit_ratio=0.0,  # Will be updated by cache monitoring
                slow_queries_count=0  # Will be updated by query analysis
            )
            
            self.logger.debug("Database metrics collected")
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to collect database metrics", error=str(e))
            raise
    
    async def collect_trading_metrics(self) -> TradingMetrics:
        """
        Collect current trading operation performance metrics.
        
        Returns:
            TradingMetrics: Current trading performance data
        """
        try:
            # This would integrate with actual trading operations
            # For now, return placeholder metrics
            metrics = TradingMetrics(
                timestamp=datetime.now(),
                order_processing_time_ms=0.0,  # Will be updated by order tracking
                signal_generation_time_ms=0.0,  # Will be updated by signal tracking
                strategy_execution_time_ms=0.0,  # Will be updated by strategy tracking
                trade_count=0  # Will be updated by trade tracking
            )
            
            self.logger.debug("Trading metrics collected")
            return metrics
            
        except Exception as e:
            self.logger.error("Failed to collect trading metrics", error=str(e))
            raise
    
    async def collect_all_metrics(self) -> Dict[str, Any]:
        """
        Collect all performance metrics.
        
        Returns:
            Dict containing all collected metrics
        """
        try:
            system_metrics = await self.collect_system_metrics()
            app_metrics = await self.collect_application_metrics()
            db_metrics = await self.collect_database_metrics()
            trading_metrics = await self.collect_trading_metrics()
            
            all_metrics = {
                'timestamp': datetime.now().isoformat(),
                'system': asdict(system_metrics),
                'application': asdict(app_metrics),
                'database': asdict(db_metrics),
                'trading': asdict(trading_metrics)
            }
            
            # Store in history
            self._store_metrics_history(all_metrics)
            
            self.logger.info("All performance metrics collected",
                           system_cpu=system_metrics.cpu_percent,
                           system_memory=system_metrics.memory_percent,
                           app_throughput=app_metrics.throughput_rps)
            
            return all_metrics
            
        except Exception as e:
            self.logger.error("Failed to collect all metrics", error=str(e))
            raise
    
    def _store_metrics_history(self, metrics: Dict[str, Any]) -> None:
        """Store metrics in history with size limit."""
        self.metrics_history.append(metrics)
        
        # Maintain history size limit
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
    
    def track_request(self, response_time_ms: float, is_error: bool = False) -> None:
        """
        Track a request for performance monitoring.
        
        Args:
            response_time_ms: Request response time in milliseconds
            is_error: Whether the request resulted in an error
        """
        self.request_count += 1
        if is_error:
            self.error_count += 1
        
        # Update Prometheus metrics
        self.response_time_histogram.observe(response_time_ms / 1000.0)
        self.throughput_counter.inc()
        if is_error:
            self.error_counter.inc()
        
        self.logger.debug("Request tracked",
                         response_time_ms=response_time_ms,
                         is_error=is_error,
                         total_requests=self.request_count)
    
    def track_database_query(self, query_time_ms: float) -> None:
        """
        Track a database query for performance monitoring.
        
        Args:
            query_time_ms: Query execution time in milliseconds
        """
        self.query_time_histogram.observe(query_time_ms / 1000.0)
        
        self.logger.debug("Database query tracked",
                         query_time_ms=query_time_ms)
    
    def track_order_processing(self, processing_time_ms: float) -> None:
        """
        Track order processing for performance monitoring.
        
        Args:
            processing_time_ms: Order processing time in milliseconds
        """
        self.order_processing_histogram.observe(processing_time_ms / 1000.0)
        
        self.logger.debug("Order processing tracked",
                         processing_time_ms=processing_time_ms)
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current performance metrics.
        
        Returns:
            Dict containing performance summary
        """
        try:
            uptime_seconds = time.time() - self.start_time
            
            summary = {
                'uptime_seconds': uptime_seconds,
                'total_requests': self.request_count,
                'total_errors': self.error_count,
                'error_rate_percent': (self.error_count / self.request_count * 100) if self.request_count > 0 else 0,
                'throughput_rps': self.request_count / uptime_seconds if uptime_seconds > 0 else 0,
                'history_size': len(self.metrics_history),
                'thresholds': self.thresholds
            }
            
            return summary
            
        except Exception as e:
            self.logger.error("Failed to get metrics summary", error=str(e))
            return {}
    
    def check_performance_thresholds(self, metrics: Dict[str, Any]) -> List[str]:
        """
        Check if performance metrics exceed thresholds.
        
        Args:
            metrics: Performance metrics to check
            
        Returns:
            List of threshold violations
        """
        violations = []
        
        try:
            system = metrics.get('system', {})
            
            # Check CPU threshold
            if system.get('cpu_percent', 0) > self.thresholds['cpu_percent']:
                violations.append(f"CPU usage {system['cpu_percent']:.1f}% exceeds threshold {self.thresholds['cpu_percent']}%")
            
            # Check memory threshold
            if system.get('memory_percent', 0) > self.thresholds['memory_percent']:
                violations.append(f"Memory usage {system['memory_percent']:.1f}% exceeds threshold {self.thresholds['memory_percent']}%")
            
            # Check disk threshold
            if system.get('disk_usage_percent', 0) > self.thresholds['disk_percent']:
                violations.append(f"Disk usage {system['disk_usage_percent']:.1f}% exceeds threshold {self.thresholds['disk_percent']}%")
            
            if violations:
                self.logger.warning("Performance threshold violations detected",
                                  violations=violations)
            
            return violations
            
        except Exception as e:
            self.logger.error("Failed to check performance thresholds", error=str(e))
            return []
    
    def get_prometheus_registry(self) -> CollectorRegistry:
        """Get the Prometheus metrics registry."""
        return self.registry
