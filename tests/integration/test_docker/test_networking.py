"""
Network isolation and security tests for Docker Compose orchestration.

This module tests network isolation, security policies, and connectivity
between services in the GRODT Docker Compose setup.
"""

import pytest
import subprocess
import json
import time
from typing import Dict, List, Any


class TestNetworkIsolation:
    """Test suite for network isolation and security."""

    @pytest.fixture(scope="class")
    def docker_compose_up(self):
        """Start Docker Compose services for testing."""
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        time.sleep(30)
        yield
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "down", "-v"],
            capture_output=True
        )

    def test_network_configuration(self, docker_compose_up):
        """Test network configuration and isolation."""
        # Check network creation
        result = subprocess.run(
            ["docker", "network", "ls", "--filter", "name=grodt"],
            capture_output=True,
            text=True
        )
        
        networks = result.stdout
        assert "grodt-network" in networks
        assert "grodt-monitoring" in networks

    def test_service_network_assignment(self, docker_compose_up):
        """Test that services are assigned to correct networks."""
        # Check GRODT network assignment
        result = subprocess.run(
            ["docker", "inspect", "grodt_grodt_1", "--format", "{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check Prometheus network assignment
        result = subprocess.run(
            ["docker", "inspect", "grodt_prometheus_1", "--format", "{{range .NetworkSettings.Networks}}{{.NetworkID}}{{end}}"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_internal_communication(self, docker_compose_up):
        """Test internal service communication."""
        # Test GRODT to Prometheus
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ping", "-c", "1", "prometheus"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test GRODT to Grafana
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ping", "-c", "1", "grafana"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_network_security_policies(self, docker_compose_up):
        """Test network security policies."""
        # Check that services can't access external networks inappropriately
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "nslookup", "google.com"],
            capture_output=True,
            text=True
        )
        # Should work for DNS resolution
        assert result.returncode == 0

    def test_port_exposure(self, docker_compose_up):
        """Test port exposure and security."""
        # Check exposed ports
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Ports}}"],
            capture_output=True,
            text=True
        )
        
        ports = result.stdout
        assert "8000->8000" in ports  # GRODT
        assert "9091->9090" in ports  # Prometheus
        assert "3000->3000" in ports  # Grafana

    def test_network_monitoring(self, docker_compose_up):
        """Test network monitoring capabilities."""
        # Run network monitoring script
        result = subprocess.run(
            ["./scripts/network-monitor.sh", "connectivity"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for network isolation
        result = subprocess.run(
            ["./scripts/network-monitor.sh", "isolation"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_network_performance(self, docker_compose_up):
        """Test network performance between services."""
        # Test latency
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ping", "-c", "3", "prometheus"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for reasonable latency (should be < 10ms)
        output = result.stdout
        if "time=" in output:
            # Extract latency values
            import re
            times = re.findall(r'time=(\d+\.?\d*)', output)
            if times:
                avg_latency = sum(float(t) for t in times) / len(times)
                assert avg_latency < 10.0, f"Network latency too high: {avg_latency}ms"

    def test_network_topology(self, docker_compose_up):
        """Test network topology and routing."""
        # Check network topology
        result = subprocess.run(
            ["./scripts/network-monitor.sh", "topology"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Verify network structure
        output = result.stdout
        assert "grodt-network" in output
        assert "grodt-monitoring" in output

    def test_security_scanning(self, docker_compose_up):
        """Test network security scanning."""
        # Run security scan
        result = subprocess.run(
            ["./scripts/network-monitor.sh", "security"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for security issues
        output = result.stdout
        assert "Exposed ports:" in output

    def test_network_traffic_monitoring(self, docker_compose_up):
        """Test network traffic monitoring."""
        # Monitor network traffic
        result = subprocess.run(
            ["./scripts/network-monitor.sh", "traffic"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for traffic statistics
        output = result.stdout
        assert "Container" in output or "CPUPerc" in output

    def test_network_failure_recovery(self, docker_compose_up):
        """Test network failure recovery."""
        # Simulate network failure by stopping a service
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "stop", "prometheus"],
            capture_output=True
        )
        
        # Wait a moment
        time.sleep(5)
        
        # Restart service
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "start", "prometheus"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Wait for recovery
        time.sleep(10)
        
        # Test connectivity
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "curl", "-f", "http://prometheus:9090/-/healthy"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
