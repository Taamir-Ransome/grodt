"""
Unit tests for system metrics collector.
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from prometheus_client import CollectorRegistry

from grodtd.monitoring.system_metrics import SystemMetricsCollector


class TestSystemMetricsCollector:
    """Test cases for SystemMetricsCollector."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Create test database
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY)")
            conn.commit()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    def test_initialization(self, temp_db):
        """Test system metrics collector initialization."""
        collector = SystemMetricsCollector(temp_db)
        
        assert collector.db_path == temp_db
        assert collector.registry is not None
        
        # Check that metrics were initialized
        assert hasattr(collector, 'api_request_duration')
        assert hasattr(collector, 'memory_usage_bytes')
        assert hasattr(collector, 'cpu_usage_percent')
        assert hasattr(collector, 'db_query_duration')
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self, temp_db):
        """Test metrics collection."""
        collector = SystemMetricsCollector(temp_db)
        
        result = await collector.collect_metrics()
        
        assert 'system' in result
        assert 'process' in result
        assert 'database' in result
        assert 'timestamp' in result
        
        # Check system metrics
        system = result['system']
        assert 'cpu' in system or 'memory' in system or 'disk' in system
    
    @pytest.mark.asyncio
    async def test_collect_system_resources(self, temp_db):
        """Test system resources collection."""
        collector = SystemMetricsCollector(temp_db)
        
        with patch('psutil.cpu_percent') as mock_cpu, \
             patch('psutil.cpu_count') as mock_cpu_count, \
             patch('psutil.virtual_memory') as mock_memory, \
             patch('psutil.swap_memory') as mock_swap, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('psutil.disk_io_counters') as mock_disk_io, \
             patch('psutil.net_io_counters') as mock_net_io:
            
            # Mock system data
            mock_cpu.return_value = 25.5
            mock_cpu_count.return_value = 8
            mock_cpu.return_value = [20.0, 30.0, 25.0, 35.0]
            
            mock_memory.return_value = Mock(
                total=8589934592,  # 8GB
                available=4294967296,  # 4GB
                used=4294967296,  # 4GB
                percent=50.0
            )
            
            mock_swap.return_value = Mock(
                total=2147483648,  # 2GB
                used=1073741824,  # 1GB
                percent=50.0
            )
            
            mock_disk.return_value = Mock(
                total=1000000000000,  # 1TB
                used=500000000000,  # 500GB
                free=500000000000  # 500GB
            )
            
            mock_disk_io.return_value = Mock(
                read_bytes=1000000,
                write_bytes=2000000
            )
            
            mock_net_io.return_value = Mock(
                bytes_sent=1000000,
                bytes_recv=2000000,
                packets_sent=1000,
                packets_recv=2000
            )
            
            system_metrics = await collector._collect_system_resources()
            
            assert 'cpu' in system_metrics
            assert 'memory' in system_metrics
            assert 'disk' in system_metrics
            assert 'network' in system_metrics
            
            # Check CPU metrics
            cpu = system_metrics['cpu']
            assert 'percent' in cpu
            assert 'count' in cpu
            assert cpu['percent'] == 25.5
            assert cpu['count'] == 8
            
            # Check memory metrics
            memory = system_metrics['memory']
            assert 'total' in memory
            assert 'used' in memory
            assert 'percent' in memory
            assert memory['total'] == 8589934592
            assert memory['percent'] == 50.0
    
    @pytest.mark.asyncio
    async def test_collect_process_metrics(self, temp_db):
        """Test process metrics collection."""
        collector = SystemMetricsCollector(temp_db)
        
        with patch('psutil.Process') as mock_process:
            # Mock process data
            mock_process_instance = Mock()
            mock_process_instance.cpu_percent.return_value = 15.5
            mock_process_instance.memory_info.return_value = Mock(rss=1000000, vms=2000000)
            mock_process_instance.memory_percent.return_value = 2.5
            mock_process_instance.num_threads.return_value = 5
            mock_process_instance.num_fds.return_value = 10
            mock_process_instance.cpu_times.return_value = Mock(user=10.0, system=5.0)
            mock_process_instance.create_time.return_value = 1609459200.0
            mock_process_instance.pid = 12345
            
            mock_process.return_value = mock_process_instance
            
            process_metrics = await collector._collect_process_metrics()
            
            assert 'pid' in process_metrics
            assert 'cpu_percent' in process_metrics
            assert 'memory_rss' in process_metrics
            assert 'memory_vms' in process_metrics
            assert 'memory_percent' in process_metrics
            assert 'num_threads' in process_metrics
            assert 'num_fds' in process_metrics
            assert 'cpu_times' in process_metrics
            assert 'create_time' in process_metrics
            
            assert process_metrics['pid'] == 12345
            assert process_metrics['cpu_percent'] == 15.5
            assert process_metrics['memory_rss'] == 1000000
            assert process_metrics['num_threads'] == 5
    
    @pytest.mark.asyncio
    async def test_collect_database_metrics(self, temp_db):
        """Test database metrics collection."""
        collector = SystemMetricsCollector(temp_db)
        
        database_metrics = await collector._collect_database_metrics()
        
        assert 'databases' in database_metrics
        assert 'tables' in database_metrics
        assert 'size_bytes' in database_metrics
        assert 'test_query_time' in database_metrics
        
        # Should have at least 1 database (the test database)
        assert database_metrics['databases'] >= 1
        assert database_metrics['tables'] >= 1
        assert database_metrics['size_bytes'] > 0
        assert database_metrics['test_query_time'] >= 0
    
    @pytest.mark.asyncio
    async def test_update_prometheus_metrics(self, temp_db):
        """Test Prometheus metrics update."""
        collector = SystemMetricsCollector(temp_db)
        
        # Mock system metrics
        system_metrics = {
            'cpu': {'percent': 25.0, 'count': 8},
            'memory': {'total': 8589934592, 'used': 4294967296, 'percent': 50.0},
            'disk': {'total': 1000000000000, 'used': 500000000000, 'percent': 50.0}
        }
        
        process_metrics = {
            'cpu_percent': 15.0,
            'memory_rss': 1000000,
            'num_threads': 5,
            'num_fds': 10
        }
        
        database_metrics = {
            'databases': 1,
            'tables': 1,
            'size_bytes': 1000000
        }
        
        # This should not raise an exception
        await collector._update_prometheus_metrics(
            system_metrics, process_metrics, database_metrics
        )
        
        # Check that metrics were set
        assert collector.cpu_usage_percent.labels(cpu_type='total')._value._value == 25.0
        assert collector.memory_usage_bytes.labels(memory_type='total')._value._value == 8589934592
        assert collector.process_cpu_percent._value._value == 15.0
    
    def test_track_api_request(self, temp_db):
        """Test API request tracking."""
        collector = SystemMetricsCollector(temp_db)
        
        # Track a successful API request
        collector.track_api_request(
            provider='robinhood',
            endpoint='/quotes',
            method='GET',
            duration=0.5,
            status_code=200
        )
        
        # Track a failed API request
        collector.track_api_request(
            provider='robinhood',
            endpoint='/orders',
            method='POST',
            duration=1.0,
            status_code=500
        )
        
        # Check that metrics were updated
        # Note: We can't easily test the exact values without more complex mocking
        # but we can verify the methods don't raise exceptions
    
    def test_track_database_query(self, temp_db):
        """Test database query tracking."""
        collector = SystemMetricsCollector(temp_db)
        
        # Track a database query
        collector.track_database_query(
            query_type='SELECT',
            table='trades',
            duration=0.01
        )
        
        # This should not raise an exception
        assert True  # If we get here, the method worked
    
    def test_track_database_error(self, temp_db):
        """Test database error tracking."""
        collector = SystemMetricsCollector(temp_db)
        
        # Track a database error
        collector.track_database_error('connection_error')
        
        # This should not raise an exception
        assert True  # If we get here, the method worked
    
    @pytest.mark.asyncio
    async def test_collect_with_psutil_error(self, temp_db):
        """Test collection with psutil error."""
        collector = SystemMetricsCollector(temp_db)
        
        # Mock psutil to raise an exception
        with patch('psutil.cpu_percent') as mock_cpu:
            mock_cpu.side_effect = Exception("psutil error")
            
            result = await collector.collect_metrics()
            
            # Should handle error gracefully
            assert 'system' in result
            assert 'process' in result
            assert 'database' in result
    
    @pytest.mark.asyncio
    async def test_collect_with_database_error(self, temp_db):
        """Test collection with database error."""
        collector = SystemMetricsCollector(temp_db)
        
        # Mock database connection to raise an exception
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = Exception("Database error")
            
            result = await collector.collect_metrics()
            
            # Should handle error gracefully
            assert 'system' in result
            assert 'process' in result
            assert 'database' in result
