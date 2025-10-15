"""
Base metrics collector for GRODT trading system.

Provides the foundation for all metrics collection with proper labeling,
asynchronous collection, and performance optimization.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from prometheus_client import (
    Counter, Histogram, Gauge, Summary, 
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from prometheus_client.core import CollectorRegistry as CoreCollectorRegistry


class MetricsCollector(ABC):
    """
    Base class for all metrics collectors in the GRODT system.
    
    Provides common functionality for:
    - Asynchronous metrics collection
    - Proper labeling and metadata
    - Performance optimization
    - Registry management
    """
    
    def __init__(self, registry: Optional[CollectorRegistry] = None):
        """
        Initialize the metrics collector.
        
        Args:
            registry: Optional Prometheus registry. If None, uses default registry.
        """
        self.registry = registry or CollectorRegistry()
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._collection_start_time = time.time()
        self._last_collection_time = 0.0
        self._collection_count = 0
        self._collector_id = id(self)  # Unique identifier for this collector instance
        
        # Performance tracking metrics - use collector type to make them unique
        collector_type = self.__class__.__name__
        self._collection_duration = Histogram(
            f'metrics_collection_duration_seconds_{collector_type.lower()}',
            'Time spent collecting metrics',
            ['collector_type'],
            registry=self.registry
        )
        
        self._collection_errors = Counter(
            f'metrics_collection_errors_total_{collector_type.lower()}',
            'Total number of metrics collection errors',
            ['collector_type', 'error_type'],
            registry=self.registry
        )
        
        self._collection_frequency = Gauge(
            f'metrics_collection_frequency_per_second_{collector_type.lower()}',
            'Metrics collection frequency',
            ['collector_type'],
            registry=self.registry
        )
        
        # Initialize collector-specific metrics
        self._initialize_metrics()
    
    @abstractmethod
    def _initialize_metrics(self) -> None:
        """Initialize collector-specific metrics. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics asynchronously. Must be implemented by subclasses.
        
        Returns:
            Dictionary containing collected metrics data
        """
        pass
    
    async def collect(self) -> Dict[str, Any]:
        """
        Main collection method with performance tracking.
        
        Returns:
            Dictionary containing collected metrics data
        """
        start_time = time.time()
        collector_type = self.__class__.__name__
        
        try:
            # Collect metrics
            metrics_data = await self.collect_metrics()
            
            # Update performance metrics
            duration = time.time() - start_time
            self._collection_duration.labels(collector_type=collector_type).observe(duration)
            
            # Update collection frequency
            current_time = time.time()
            if self._last_collection_time > 0:
                time_diff = current_time - self._last_collection_time
                if time_diff > 0:
                    frequency = 1.0 / time_diff
                    self._collection_frequency.labels(collector_type=collector_type).set(frequency)
            
            self._last_collection_time = current_time
            self._collection_count += 1
            
            self.logger.debug(f"Collected {len(metrics_data)} metrics in {duration:.4f}s")
            return metrics_data
            
        except Exception as e:
            # Track collection errors
            error_type = type(e).__name__
            self._collection_errors.labels(
                collector_type=collector_type,
                error_type=error_type
            ).inc()
            
            self.logger.error(f"Error collecting metrics: {e}")
            raise
    
    def get_registry(self) -> CollectorRegistry:
        """Get the Prometheus registry for this collector."""
        return self.registry
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of collection performance.
        
        Returns:
            Dictionary with collection statistics
        """
        current_time = time.time()
        uptime = current_time - self._collection_start_time
        
        return {
            'collector_type': self.__class__.__name__,
            'uptime_seconds': uptime,
            'collection_count': self._collection_count,
            'last_collection_time': self._last_collection_time,
            'average_frequency_per_second': self._collection_count / uptime if uptime > 0 else 0
        }
    
    def create_common_labels(self, 
                           strategy: Optional[str] = None,
                           symbol: Optional[str] = None,
                           regime: Optional[str] = None) -> Dict[str, str]:
        """
        Create common labels for metrics.
        
        Args:
            strategy: Trading strategy name
            symbol: Trading symbol
            regime: Market regime
            
        Returns:
            Dictionary of common labels
        """
        labels = {
            'system': 'grodt',
            'version': '0.1.0'
        }
        
        if strategy:
            labels['strategy'] = strategy
        if symbol:
            labels['symbol'] = symbol
        if regime:
            labels['regime'] = regime
            
        return labels
    
    def create_counter(self,
                       name: str,
                       description: str,
                       labelnames: Optional[List[str]] = None,
                       **label_kwargs) -> Counter:
        """
        Create a Counter metric.
        
        Args:
            name: Metric name
            description: Metric description
            labelnames: List of label names
            **label_kwargs: Additional labels (ignored for now)
            
        Returns:
            Counter metric
        """
        return Counter(
            name,
            description,
            labelnames or [],
            registry=self.registry
        )
    
    def create_histogram(self,
                        name: str,
                        description: str,
                        labelnames: Optional[List[str]] = None,
                        buckets: Optional[List[float]] = None,
                        **label_kwargs) -> Histogram:
        """
        Create a Histogram metric.
        
        Args:
            name: Metric name
            description: Metric description
            labelnames: List of label names
            buckets: Histogram buckets
            **label_kwargs: Additional labels (ignored for now)
            
        Returns:
            Histogram metric
        """
        return Histogram(
            name,
            description,
            labelnames or [],
            buckets=buckets,
            registry=self.registry
        )
    
    def create_gauge(self,
                    name: str,
                    description: str,
                    labelnames: Optional[List[str]] = None,
                    **label_kwargs) -> Gauge:
        """
        Create a Gauge metric.
        
        Args:
            name: Metric name
            description: Metric description
            labelnames: List of label names
            **label_kwargs: Additional labels (ignored for now)
            
        Returns:
            Gauge metric
        """
        return Gauge(
            name,
            description,
            labelnames or [],
            registry=self.registry
        )
    
    def create_summary(self,
                      name: str,
                      description: str,
                      labelnames: Optional[List[str]] = None,
                      **label_kwargs) -> Summary:
        """
        Create a Summary metric.
        
        Args:
            name: Metric name
            description: Metric description
            labelnames: List of label names
            **label_kwargs: Additional labels (ignored for now)
            
        Returns:
            Summary metric
        """
        return Summary(
            name,
            description,
            labelnames or [],
            registry=self.registry
        )
