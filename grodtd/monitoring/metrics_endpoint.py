"""
Metrics endpoint for Prometheus scraping.

Provides the `/metrics` endpoint that Prometheus can scrape to collect
all system metrics including trading, system, and business metrics.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from flask import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, CollectorRegistry

from .metrics_collector import MetricsCollector
from .trading_metrics import TradingMetricsCollector
from .system_metrics import SystemMetricsCollector
from .business_metrics import BusinessMetricsCollector


class MetricsEndpoint:
    """
    Metrics endpoint handler for Prometheus scraping.
    
    Manages all metrics collectors and provides the `/metrics` endpoint
    that Prometheus can scrape for time-series data collection.
    """
    
    def __init__(self, db_path: str):
        """
        Initialize metrics endpoint.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        
        # Create a custom registry for all metrics
        self.registry = CollectorRegistry()
        
        # Initialize metrics collectors
        self.trading_collector = TradingMetricsCollector(db_path, self.registry)
        self.system_collector = SystemMetricsCollector(db_path, self.registry)
        self.business_collector = BusinessMetricsCollector(db_path, self.registry)
        
        # Collection state
        self._last_collection_time = 0.0
        self._collection_interval = 1.0  # Collect every second
        self._is_collecting = False
        
        self.logger.info("Metrics endpoint initialized")
    
    async def collect_all_metrics(self) -> Dict[str, Any]:
        """
        Collect metrics from all collectors asynchronously.
        
        Returns:
            Dictionary containing all collected metrics
        """
        try:
            # Collect metrics from all collectors in parallel
            tasks = [
                self.trading_collector.collect(),
                self.system_collector.collect(),
                self.business_collector.collect()
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            metrics_data = {
                'trading': results[0] if not isinstance(results[0], Exception) else {},
                'system': results[1] if not isinstance(results[1], Exception) else {},
                'business': results[2] if not isinstance(results[2], Exception) else {},
                'timestamp': asyncio.get_event_loop().time()
            }
            
            # Log any collection errors
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    collector_names = ['trading', 'system', 'business']
                    self.logger.error(f"Error collecting {collector_names[i]} metrics: {result}")
            
            return metrics_data
            
        except Exception as e:
            self.logger.error(f"Error collecting all metrics: {e}")
            return {}
    
    def get_metrics_response(self) -> Response:
        """
        Get the Prometheus metrics response.
        
        Returns:
            Flask Response with Prometheus metrics data
        """
        try:
            # Generate metrics in Prometheus format
            metrics_data = generate_latest(self.registry)
            
            return Response(
                metrics_data,
                mimetype=CONTENT_TYPE_LATEST,
                headers={
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error generating metrics response: {e}")
            return Response(
                f"# Error generating metrics: {e}\n",
                mimetype=CONTENT_TYPE_LATEST,
                status=500
            )
    
    async def start_continuous_collection(self) -> None:
        """
        Start continuous metrics collection in the background.
        
        This method should be called to start the background collection
        process that updates metrics at regular intervals.
        """
        if self._is_collecting:
            self.logger.warning("Continuous collection already running")
            return
        
        self._is_collecting = True
        self.logger.info("Starting continuous metrics collection")
        
        try:
            while self._is_collecting:
                # Collect metrics
                await self.collect_all_metrics()
                
                # Wait for next collection interval
                await asyncio.sleep(self._collection_interval)
                
        except Exception as e:
            self.logger.error(f"Error in continuous collection: {e}")
        finally:
            self._is_collecting = False
    
    def stop_continuous_collection(self) -> None:
        """Stop continuous metrics collection."""
        self._is_collecting = False
        self.logger.info("Stopped continuous metrics collection")
    
    def get_collection_status(self) -> Dict[str, Any]:
        """
        Get the status of metrics collection.
        
        Returns:
            Dictionary with collection status information
        """
        return {
            'is_collecting': self._is_collecting,
            'collection_interval': self._collection_interval,
            'last_collection_time': self._last_collection_time,
            'collectors': {
                'trading': self.trading_collector.get_metrics_summary(),
                'system': self.system_collector.get_metrics_summary(),
                'business': self.business_collector.get_metrics_summary()
            }
        }
    
    def set_collection_interval(self, interval: float) -> None:
        """
        Set the metrics collection interval.
        
        Args:
            interval: Collection interval in seconds
        """
        if interval <= 0:
            raise ValueError("Collection interval must be positive")
        
        self._collection_interval = interval
        self.logger.info(f"Set collection interval to {interval} seconds")
    
    def get_registry(self) -> CollectorRegistry:
        """Get the Prometheus registry."""
        return self.registry
    
    def add_custom_metric(self, metric) -> None:
        """
        Add a custom metric to the registry.
        
        Args:
            metric: Prometheus metric to add
        """
        self.registry.register(metric)
        self.logger.debug(f"Added custom metric: {metric}")
    
    def remove_custom_metric(self, metric) -> None:
        """
        Remove a custom metric from the registry.
        
        Args:
            metric: Prometheus metric to remove
        """
        self.registry.unregister(metric)
        self.logger.debug(f"Removed custom metric: {metric}")


def create_metrics_endpoint(db_path: str) -> MetricsEndpoint:
    """
    Create a metrics endpoint instance.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        MetricsEndpoint instance
    """
    return MetricsEndpoint(db_path)
