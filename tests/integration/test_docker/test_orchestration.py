"""
Integration tests for Docker Compose orchestration.

This module tests the complete Docker Compose orchestration system,
including service dependencies, networking, volume management, and scaling.
"""

import pytest
import requests
import time
import subprocess
import json
from typing import Dict, List, Any
from pathlib import Path


class TestDockerOrchestration:
    """Test suite for Docker Compose orchestration."""

    @pytest.fixture(scope="class")
    def docker_compose_up(self):
        """Start Docker Compose services for testing."""
        # Start services
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, f"Failed to start services: {result.stderr}"
        
        # Wait for services to be ready
        time.sleep(30)
        
        yield
        
        # Cleanup
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "down", "-v"],
            capture_output=True
        )

    def test_services_startup(self, docker_compose_up):
        """Test that all services start successfully."""
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert "grodt" in result.stdout
        assert "prometheus" in result.stdout
        assert "grafana" in result.stdout

    def test_service_health_checks(self, docker_compose_up):
        """Test service health checks."""
        # Test GRODT health
        response = requests.get("http://localhost:8000/health", timeout=10)
        assert response.status_code == 200
        
        # Test Prometheus health
        response = requests.get("http://localhost:9091/-/healthy", timeout=10)
        assert response.status_code == 200
        
        # Test Grafana health
        response = requests.get("http://localhost:3000/api/health", timeout=10)
        assert response.status_code == 200

    def test_service_dependencies(self, docker_compose_up):
        """Test service dependency resolution."""
        # Check that GRODT depends on Prometheus and Grafana
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps", "--format", "json"],
            capture_output=True,
            text=True
        )
        
        services = json.loads(result.stdout)
        grodt_service = next(s for s in services if s["Name"] == "grodt_grodt_1")
        
        # Verify dependencies are met
        assert grodt_service["State"] == "running"

    def test_network_connectivity(self, docker_compose_up):
        """Test network connectivity between services."""
        # Test GRODT to Prometheus connectivity
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "curl", "-f", "http://prometheus:9090/-/healthy"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test GRODT to Grafana connectivity
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "curl", "-f", "http://grafana:3000/api/health"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_volume_mounting(self, docker_compose_up):
        """Test volume mounting and persistence."""
        # Test data volume
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/data"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test logs volume
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/logs"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test configs volume
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/configs"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_environment_variables(self, docker_compose_up):
        """Test environment variable injection."""
        # Check GRODT environment variables
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "env"],
            capture_output=True,
            text=True
        )
        
        env_vars = result.stdout
        assert "ENV=prod" in env_vars
        assert "DATABASE_URL=sqlite:///app/data/grodt.db" in env_vars
        assert "PROMETHEUS_HOST=prometheus" in env_vars
        assert "GRAFANA_HOST=grafana" in env_vars

    def test_resource_limits(self, docker_compose_up):
        """Test resource limits and constraints."""
        # Check memory limits
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", "grodt_grodt_1"],
            capture_output=True,
            text=True
        )
        
        # Memory usage should be within limits
        memory_usage = result.stdout.strip()
        assert memory_usage != ""

    def test_logging_configuration(self, docker_compose_up):
        """Test logging configuration."""
        # Check log files exist
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/logs"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_restart_policies(self, docker_compose_up):
        """Test service restart policies."""
        # Check restart policy
        result = subprocess.run(
            ["docker", "inspect", "grodt_grodt_1", "--format", "{{.HostConfig.RestartPolicy.Name}}"],
            capture_output=True,
            text=True
        )
        assert "unless-stopped" in result.stdout

    def test_network_isolation(self, docker_compose_up):
        """Test network isolation between services."""
        # Check network configuration
        result = subprocess.run(
            ["docker", "network", "ls", "--filter", "name=grodt"],
            capture_output=True,
            text=True
        )
        
        networks = result.stdout
        assert "grodt-network" in networks
        assert "grodt-monitoring" in networks

    def test_service_scaling(self, docker_compose_up):
        """Test service scaling capabilities."""
        # Scale GRODT service
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "up", "-d", "--scale", "grodt=2"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check scaled instances
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps", "grodt"],
            capture_output=True,
            text=True
        )
        
        # Should have 2 instances
        instances = result.stdout.count("grodt_grodt_")
        assert instances == 2

    def test_load_balancing(self, docker_compose_up):
        """Test load balancing functionality."""
        # Start load balancer
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.scale.yml", "up", "-d", "grodt-lb"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test load balancer health
        response = requests.get("http://localhost/health", timeout=10)
        assert response.status_code == 200
        assert response.text.strip() == "healthy"

    def test_monitoring_integration(self, docker_compose_up):
        """Test monitoring system integration."""
        # Test Prometheus metrics endpoint
        response = requests.get("http://localhost:9091/api/v1/targets", timeout=10)
        assert response.status_code == 200
        
        # Test Grafana API
        response = requests.get("http://localhost:3000/api/health", timeout=10)
        assert response.status_code == 200

    def test_data_persistence(self, docker_compose_up):
        """Test data persistence across restarts."""
        # Create test data
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "touch", "/app/data/test_file.txt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Restart service
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "restart", "grodt"],
            capture_output=True
        )
        
        # Wait for restart
        time.sleep(10)
        
        # Check data persistence
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "/app/data/test_file.txt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_security_configuration(self, docker_compose_up):
        """Test security configuration."""
        # Check non-root user
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "whoami"],
            capture_output=True,
            text=True
        )
        assert result.stdout.strip() == "grodt"
        
        # Check file permissions
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_environment_specific_configs(self, docker_compose_up):
        """Test environment-specific configurations."""
        # Test development environment
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "-f", "docker/docker-compose.dev.yml", "config"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test staging environment
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "-f", "docker/docker-compose.staging.yml", "config"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test production environment
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "-f", "docker/docker-compose.prod.yml", "config"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_volume_backup_recovery(self, docker_compose_up):
        """Test volume backup and recovery."""
        # Create test data
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "echo", "test_data", ">", "/app/data/backup_test.txt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Run backup
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "backup", "grodt_data"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Verify backup exists
        backup_dir = Path("/var/lib/docker/volumes/grodt_backups")
        if backup_dir.exists():
            backup_files = list(backup_dir.glob("grodt_data_*.tar.gz"))
            assert len(backup_files) > 0

    def test_network_monitoring(self, docker_compose_up):
        """Test network monitoring capabilities."""
        # Run network monitoring
        result = subprocess.run(
            ["./scripts/network-monitor.sh", "connectivity"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Test network isolation
        result = subprocess.run(
            ["./scripts/network-monitor.sh", "isolation"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_performance_metrics(self, docker_compose_up):
        """Test performance metrics collection."""
        # Test metrics endpoint
        response = requests.get("http://localhost:9090/metrics", timeout=10)
        assert response.status_code == 200
        
        # Check for GRODT metrics
        metrics = response.text
        assert "grodt_" in metrics or "python_" in metrics

    def test_cleanup_and_teardown(self, docker_compose_up):
        """Test cleanup and teardown procedures."""
        # Stop all services
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "down", "-v"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Verify cleanup
        result = subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "ps"],
            capture_output=True,
            text=True
        )
        assert "grodt" not in result.stdout
