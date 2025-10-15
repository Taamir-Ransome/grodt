"""
Service scaling and load balancing tests for Docker Compose orchestration.

This module tests service scaling, load balancing, and performance
in the GRODT Docker Compose setup.
"""

import pytest
import subprocess
import requests
import time
import json
from typing import Dict, List, Any


class TestServiceScaling:
    """Test suite for service scaling and load balancing."""

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

    def test_service_scaling(self, docker_compose_up):
        """Test service scaling functionality."""
        # Scale GRODT service to 3 instances
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=3"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Wait for scaling
        time.sleep(20)
        
        # Check scaled instances
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps", "grodt"],
            capture_output=True,
            text=True
        )
        
        # Should have 3 instances
        instances = result.stdout.count("grodt_grodt_")
        assert instances == 3

    def test_load_balancer_startup(self, docker_compose_up):
        """Test load balancer startup."""
        # Start load balancer
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "up", "-d", "grodt-lb"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Wait for load balancer
        time.sleep(10)
        
        # Check load balancer is running
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "ps", "grodt-lb"],
            capture_output=True,
            text=True
        )
        assert "grodt-lb" in result.stdout

    def test_load_balancer_health(self, docker_compose_up):
        """Test load balancer health check."""
        # Start load balancer
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "up", "-d", "grodt-lb"],
            capture_output=True
        )
        time.sleep(10)
        
        # Test load balancer health
        response = requests.get("http://localhost/health", timeout=10)
        assert response.status_code == 200
        assert response.text.strip() == "healthy"

    def test_load_balancing_distribution(self, docker_compose_up):
        """Test load balancing request distribution."""
        # Scale to multiple instances
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=3"],
            capture_output=True
        )
        time.sleep(20)
        
        # Start load balancer
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "up", "-d", "grodt-lb"],
            capture_output=True
        )
        time.sleep(10)
        
        # Send multiple requests
        responses = []
        for i in range(10):
            try:
                response = requests.get("http://localhost/health", timeout=5)
                responses.append(response.status_code)
            except requests.exceptions.RequestException:
                pass
            time.sleep(0.5)
        
        # Most requests should succeed
        success_count = sum(1 for code in responses if code == 200)
        assert success_count >= 5, f"Only {success_count}/10 requests succeeded"

    def test_service_discovery(self, docker_compose_up):
        """Test service discovery functionality."""
        # Start service discovery
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "up", "-d", "service-discovery"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Wait for service discovery
        time.sleep(15)
        
        # Check service discovery is running
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "ps", "service-discovery"],
            capture_output=True,
            text=True
        )
        assert "service-discovery" in result.stdout

    def test_auto_scaling(self, docker_compose_up):
        """Test auto-scaling functionality."""
        # Run auto-scaling
        result = subprocess.run(
            ["./scripts/scale-manager.sh", "auto-scale"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for scaling decisions
        output = result.stdout
        assert "Current CPU usage:" in output
        assert "Current replicas:" in output

    def test_performance_monitoring(self, docker_compose_up):
        """Test performance monitoring."""
        # Run performance monitoring
        result = subprocess.run(
            ["./scripts/scale-manager.sh", "monitor"],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0
        
        # Check for performance metrics
        output = result.stdout
        assert "CPU:" in output
        assert "Memory:" in output

    def test_service_health_checks(self, docker_compose_up):
        """Test service health checks in scaled environment."""
        # Scale service
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=2"],
            capture_output=True
        )
        time.sleep(20)
        
        # Check health of all instances
        result = subprocess.run(
            ["./scripts/scale-manager.sh", "health", "grodt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for health information
        output = result.stdout
        assert "Instance" in output

    def test_service_status_monitoring(self, docker_compose_up):
        """Test service status monitoring."""
        # Get service status
        result = subprocess.run(
            ["./scripts/scale-manager.sh", "status"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for status information
        output = result.stdout
        assert "Service Status:" in output
        assert "Resource Usage:" in output

    def test_load_balancer_restart(self, docker_compose_up):
        """Test load balancer restart functionality."""
        # Start load balancer
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "up", "-d", "grodt-lb"],
            capture_output=True
        )
        time.sleep(10)
        
        # Restart load balancer
        result = subprocess.run(
            ["./scripts/scale-manager.sh", "lb-restart"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check load balancer is still running
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "ps", "grodt-lb"],
            capture_output=True,
            text=True
        )
        assert "grodt-lb" in result.stdout

    def test_scaling_limits(self, docker_compose_up):
        """Test scaling limits and constraints."""
        # Try to scale beyond limits
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=10"],
            capture_output=True,
            text=True
        )
        
        # Should either succeed or fail gracefully
        if result.returncode != 0:
            # Check for resource constraints
            assert "resource" in result.stderr.lower() or "limit" in result.stderr.lower()

    def test_rolling_updates(self, docker_compose_up):
        """Test rolling updates functionality."""
        # Scale service
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=2"],
            capture_output=True
        )
        time.sleep(20)
        
        # Perform rolling update
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--no-deps", "grodt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check services are still running
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps", "grodt"],
            capture_output=True,
            text=True
        )
        assert "grodt_grodt_" in result.stdout

    def test_failure_recovery(self, docker_compose_up):
        """Test failure recovery in scaled environment."""
        # Scale service
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=3"],
            capture_output=True
        )
        time.sleep(20)
        
        # Stop one instance
        subprocess.run(
            ["docker", "stop", "grodt_grodt_1"],
            capture_output=True
        )
        time.sleep(5)
        
        # Check that other instances are still running
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps", "grodt"],
            capture_output=True,
            text=True
        )
        
        # Should still have running instances
        running_instances = result.stdout.count("Up")
        assert running_instances > 0

    def test_load_balancer_configuration(self, docker_compose_up):
        """Test load balancer configuration."""
        # Check Nginx configuration
        nginx_config = Path("docker/nginx/nginx.conf")
        assert nginx_config.exists()
        
        # Check configuration content
        config_content = nginx_config.read_text()
        assert "upstream grodt_backend" in config_content
        assert "least_conn" in config_content
        assert "max_fails=3" in config_content

    def test_metrics_collection(self, docker_compose_up):
        """Test metrics collection in scaled environment."""
        # Scale service
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=2"],
            capture_output=True
        )
        time.sleep(20)
        
        # Check metrics endpoint
        response = requests.get("http://localhost:9090/metrics", timeout=10)
        assert response.status_code == 200
        
        # Check for GRODT metrics
        metrics = response.text
        assert "grodt_" in metrics or "python_" in metrics

    def test_cleanup_scaled_services(self, docker_compose_up):
        """Test cleanup of scaled services."""
        # Scale service
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=3"],
            capture_output=True
        )
        time.sleep(20)
        
        # Stop all services
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "down", "-v"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check cleanup
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps"],
            capture_output=True,
            text=True
        )
        assert "grodt" not in result.stdout
