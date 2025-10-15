"""
System metrics collector for GRODT trading system.

Collects system performance metrics including:
- API latency tracking for Robinhood API calls
- Error rate monitoring for API failures
- Memory usage tracking with garbage collection metrics
- System resource monitoring (CPU, disk usage)
- Database performance metrics
"""

import asyncio
import logging
import psutil
import time
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from prometheus_client import Counter, Histogram, Gauge, Summary

from .metrics_collector import MetricsCollector


class SystemMetricsCollector(MetricsCollector):
    """
    Collects system performance metrics for the GRODT system.
    
    Metrics include:
    - API latency and error rates
    - Memory and CPU usage
    - Database performance
    - System resource utilization
    """
    
    def __init__(self, db_path: str, registry: Optional[Any] = None):
        """
        Initialize system metrics collector.
        
        Args:
            db_path: Path to SQLite database
            registry: Optional Prometheus registry
        """
        self.db_path = db_path
        super().__init__(registry)
    
    def _initialize_metrics(self) -> None:
        """Initialize system-specific metrics."""
        
        # API Metrics
        self.api_request_duration = self.create_histogram(
            'api_request_duration_seconds',
            'API request duration',
            ['api_provider', 'endpoint', 'method'],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        )
        
        self.api_requests_total = self.create_counter(
            'api_requests_total',
            'Total API requests',
            ['api_provider', 'endpoint', 'method', 'status_code']
        )
        
        self.api_errors_total = self.create_counter(
            'api_errors_total',
            'Total API errors',
            ['api_provider', 'endpoint', 'error_type']
        )
        
        self.api_rate_limit_remaining = self.create_gauge(
            'api_rate_limit_remaining',
            'Remaining API rate limit',
            ['api_provider']
        )
        
        # Memory Metrics
        self.memory_usage_bytes = self.create_gauge(
            'system_memory_usage_bytes',
            'Memory usage in bytes',
            ['memory_type']
        )
        
        self.memory_usage_percent = self.create_gauge(
            'system_memory_usage_percent',
            'Memory usage percentage',
            ['memory_type']
        )
        
        self.gc_collections_total = self.create_counter(
            'python_gc_collections_total',
            'Python garbage collection events',
            ['generation']
        )
        
        # CPU Metrics
        self.cpu_usage_percent = self.create_gauge(
            'system_cpu_usage_percent',
            'CPU usage percentage',
            ['cpu_type']
        )
        
        self.cpu_count = self.create_gauge(
            'system_cpu_count',
            'Number of CPU cores'
        )
        
        # Disk Metrics
        self.disk_usage_bytes = self.create_gauge(
            'system_disk_usage_bytes',
            'Disk usage in bytes',
            ['disk_type', 'mount_point']
        )
        
        self.disk_usage_percent = self.create_gauge(
            'system_disk_usage_percent',
            'Disk usage percentage',
            ['disk_type', 'mount_point']
        )
        
        # Database Metrics
        self.db_query_duration = self.create_histogram(
            'database_query_duration_seconds',
            'Database query duration',
            ['query_type', 'table'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )
        
        self.db_connections_active = self.create_gauge(
            'database_connections_active',
            'Active database connections'
        )
        
        self.db_connections_total = self.create_counter(
            'database_connections_total',
            'Total database connections',
            ['connection_type']
        )
        
        self.db_errors_total = self.create_counter(
            'database_errors_total',
            'Total database errors',
            ['error_type']
        )
        
        # Process Metrics
        self.process_cpu_percent = self.create_gauge(
            'process_cpu_percent',
            'Process CPU usage percentage'
        )
        
        self.process_memory_bytes = self.create_gauge(
            'process_memory_bytes',
            'Process memory usage in bytes'
        )
        
        self.process_threads = self.create_gauge(
            'process_threads',
            'Number of process threads'
        )
        
        self.process_open_files = self.create_gauge(
            'process_open_files',
            'Number of open file descriptors'
        )
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect system metrics.
        
        Returns:
            Dictionary containing system metrics data
        """
        try:
            # Collect system resource metrics
            system_metrics = await self._collect_system_resources()
            
            # Collect process metrics
            process_metrics = await self._collect_process_metrics()
            
            # Collect database metrics
            database_metrics = await self._collect_database_metrics()
            
            # Update Prometheus metrics
            await self._update_prometheus_metrics(system_metrics, process_metrics, database_metrics)
            
            return {
                'system': system_metrics,
                'process': process_metrics,
                'database': database_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
            raise
    
    async def _collect_system_resources(self) -> Dict[str, Any]:
        """Collect system resource metrics."""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            network_io = psutil.net_io_counters()
            
            return {
                'cpu': {
                    'percent': cpu_percent,
                    'count': cpu_count,
                    'per_core': cpu_per_core
                },
                'memory': {
                    'total': memory.total,
                    'available': memory.available,
                    'used': memory.used,
                    'percent': memory.percent,
                    'swap_total': swap.total,
                    'swap_used': swap.used,
                    'swap_percent': swap.percent
                },
                'disk': {
                    'total': disk_usage.total,
                    'used': disk_usage.used,
                    'free': disk_usage.free,
                    'percent': (disk_usage.used / disk_usage.total) * 100,
                    'read_bytes': disk_io.read_bytes if disk_io else 0,
                    'write_bytes': disk_io.write_bytes if disk_io else 0
                },
                'network': {
                    'bytes_sent': network_io.bytes_sent if network_io else 0,
                    'bytes_recv': network_io.bytes_recv if network_io else 0,
                    'packets_sent': network_io.packets_sent if network_io else 0,
                    'packets_recv': network_io.packets_recv if network_io else 0
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting system resources: {e}")
            return {}
    
    async def _collect_process_metrics(self) -> Dict[str, Any]:
        """Collect process-specific metrics."""
        try:
            process = psutil.Process()
            
            # Process info
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # Thread and file info
            num_threads = process.num_threads()
            num_fds = process.num_fds() if hasattr(process, 'num_fds') else 0
            
            # Process times
            times = process.cpu_times()
            
            return {
                'pid': process.pid,
                'cpu_percent': cpu_percent,
                'memory_rss': memory_info.rss,
                'memory_vms': memory_info.vms,
                'memory_percent': memory_percent,
                'num_threads': num_threads,
                'num_fds': num_fds,
                'cpu_times': {
                    'user': times.user,
                    'system': times.system
                },
                'create_time': process.create_time()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting process metrics: {e}")
            return {}
    
    async def _collect_database_metrics(self) -> Dict[str, Any]:
        """Collect database performance metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get database info
                cursor.execute("PRAGMA database_list")
                databases = cursor.fetchall()
                
                # Get table info
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = cursor.fetchall()
                
                # Get database size
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]
                
                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]
                
                db_size = page_count * page_size
                
                # Test query performance
                start_time = time.time()
                cursor.execute("SELECT COUNT(*) FROM trades")
                trade_count = cursor.fetchone()[0]
                query_time = time.time() - start_time
                
                return {
                    'databases': len(databases),
                    'tables': len(tables),
                    'size_bytes': db_size,
                    'trade_count': trade_count,
                    'test_query_time': query_time
                }
                
        except Exception as e:
            self.logger.error(f"Error collecting database metrics: {e}")
            return {}
    
    async def _update_prometheus_metrics(self,
                                       system_metrics: Dict[str, Any],
                                       process_metrics: Dict[str, Any],
                                       database_metrics: Dict[str, Any]) -> None:
        """Update Prometheus metrics with collected data."""
        
        # Update CPU metrics
        if 'cpu' in system_metrics:
            cpu_data = system_metrics['cpu']
            self.cpu_usage_percent.labels(cpu_type='total').set(cpu_data['percent'])
            self.cpu_count.set(cpu_data['count'])
        
        # Update memory metrics
        if 'memory' in system_metrics:
            memory_data = system_metrics['memory']
            self.memory_usage_bytes.labels(memory_type='total').set(memory_data['total'])
            self.memory_usage_bytes.labels(memory_type='used').set(memory_data['used'])
            self.memory_usage_percent.labels(memory_type='total').set(memory_data['percent'])
        
        # Update disk metrics
        if 'disk' in system_metrics:
            disk_data = system_metrics['disk']
            self.disk_usage_bytes.labels(
                disk_type='total', 
                mount_point='/'
            ).set(disk_data['total'])
            self.disk_usage_bytes.labels(
                disk_type='used', 
                mount_point='/'
            ).set(disk_data['used'])
            self.disk_usage_percent.labels(
                disk_type='used', 
                mount_point='/'
            ).set(disk_data['percent'])
        
        # Update process metrics
        if process_metrics:
            self.process_cpu_percent.set(process_metrics.get('cpu_percent', 0))
            self.process_memory_bytes.set(process_metrics.get('memory_rss', 0))
            self.process_threads.set(process_metrics.get('num_threads', 0))
            self.process_open_files.set(process_metrics.get('num_fds', 0))
        
        # Update database metrics
        if database_metrics:
            self.db_connections_active.set(database_metrics.get('databases', 0))
    
    def track_api_request(self, 
                         provider: str, 
                         endpoint: str, 
                         method: str,
                         duration: float,
                         status_code: int = 200) -> None:
        """
        Track an API request for metrics collection.
        
        Args:
            provider: API provider (e.g., 'robinhood')
            endpoint: API endpoint
            method: HTTP method
            duration: Request duration in seconds
            status_code: HTTP status code
        """
        # Update request duration histogram
        self.api_request_duration.labels(
            api_provider=provider,
            endpoint=endpoint,
            method=method
        ).observe(duration)
        
        # Update request counter
        self.api_requests_total.labels(
            api_provider=provider,
            endpoint=endpoint,
            method=method,
            status_code=str(status_code)
        ).inc()
        
        # Track errors
        if status_code >= 400:
            error_type = 'client_error' if status_code < 500 else 'server_error'
            self.api_errors_total.labels(
                api_provider=provider,
                endpoint=endpoint,
                error_type=error_type
            ).inc()
    
    def track_database_query(self, 
                           query_type: str, 
                           table: str, 
                           duration: float) -> None:
        """
        Track a database query for metrics collection.
        
        Args:
            query_type: Type of query (SELECT, INSERT, UPDATE, DELETE)
            table: Database table name
            duration: Query duration in seconds
        """
        self.db_query_duration.labels(
            query_type=query_type,
            table=table
        ).observe(duration)
    
    def track_database_error(self, error_type: str) -> None:
        """
        Track a database error.
        
        Args:
            error_type: Type of database error
        """
        self.db_errors_total.labels(error_type=error_type).inc()
