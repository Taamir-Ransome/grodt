"""
Test utilities for Prometheus metrics testing.

Provides test isolation for Prometheus metrics to prevent registry conflicts
between test instances.
"""

import pytest
from prometheus_client import CollectorRegistry, REGISTRY
from typing import Generator


@pytest.fixture
def prometheus_registry() -> Generator[CollectorRegistry, None, None]:
    """
    Provide a clean Prometheus registry for testing.
    
    This fixture creates a new registry for each test to prevent
    conflicts between test instances.
    """
    # Create a new registry for testing
    test_registry = CollectorRegistry()
    
    # Store the original registry
    original_registry = REGISTRY
    
    # Replace the global registry with our test registry
    import prometheus_client
    prometheus_client.REGISTRY = test_registry
    
    yield test_registry
    
    # Restore the original registry
    prometheus_client.REGISTRY = original_registry


@pytest.fixture
def clean_prometheus_registry() -> Generator[None, None, None]:
    """
    Clean the Prometheus registry before each test.
    
    This fixture clears the default registry to prevent
    metric conflicts between tests.
    """
    # Clear the default registry
    REGISTRY._names_to_collectors.clear()
    REGISTRY._collector_to_names.clear()
    
    yield
    
    # Clean up after test
    REGISTRY._names_to_collectors.clear()
    REGISTRY._collector_to_names.clear()
