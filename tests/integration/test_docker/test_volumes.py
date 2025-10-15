"""
Volume management and persistence tests for Docker Compose orchestration.

This module tests volume mounting, data persistence, backup, and recovery
in the GRODT Docker Compose setup.
"""

import pytest
import subprocess
import time
import os
from pathlib import Path
from typing import Dict, List, Any


class TestVolumeManagement:
    """Test suite for volume management and persistence."""

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

    def test_volume_creation(self, docker_compose_up):
        """Test that volumes are created correctly."""
        # Check volume creation
        result = subprocess.run(
            ["docker", "volume", "ls", "--filter", "name=grodt"],
            capture_output=True,
            text=True
        )
        
        volumes = result.stdout
        assert "grodt_data" in volumes
        assert "grodt_logs" in volumes
        assert "grodt_configs" in volumes
        assert "prometheus_data" in volumes
        assert "grafana_data" in volumes

    def test_volume_mounting(self, docker_compose_up):
        """Test volume mounting in containers."""
        # Check GRODT data volume
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/data"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check GRODT logs volume
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/logs"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check GRODT configs volume
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/configs"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0

    def test_data_persistence(self, docker_compose_up):
        """Test data persistence across container restarts."""
        # Create test data
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "touch", "/app/data/persistence_test.txt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Write test content
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "sh", "-c", "echo 'test data' > /app/data/persistence_test.txt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Restart container
        subprocess.run(
            ["docker-compose", "-f", "docker/docker-compose.yml", "restart", "grodt"],
            capture_output=True
        )
        time.sleep(10)
        
        # Check data persistence
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "cat", "/app/data/persistence_test.txt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert "test data" in result.stdout

    def test_volume_permissions(self, docker_compose_up):
        """Test volume permissions and ownership."""
        # Check file permissions
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "-la", "/app/data"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check ownership
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "stat", "-c", "%U:%G", "/app/data"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        # Should be owned by grodt user
        assert "grodt:grodt" in result.stdout

    def test_volume_backup(self, docker_compose_up):
        """Test volume backup functionality."""
        # Create test data
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "sh", "-c", "echo 'backup test' > /app/data/backup_test.txt"],
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
        
        # Check backup was created
        backup_dir = Path("/var/lib/docker/volumes/grodt_backups")
        if backup_dir.exists():
            backup_files = list(backup_dir.glob("grodt_data_*.tar.gz"))
            assert len(backup_files) > 0

    def test_volume_restore(self, docker_compose_up):
        """Test volume restore functionality."""
        # Create test data
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "sh", "-c", "echo 'restore test' > /app/data/restore_test.txt"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Create backup
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "backup", "grodt_data"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Get backup filename
        backup_dir = Path("/var/lib/docker/volumes/grodt_backups")
        if backup_dir.exists():
            backup_files = list(backup_dir.glob("grodt_data_*.tar.gz"))
            if backup_files:
                backup_file = backup_files[0].name
                
                # Remove test data
                result = subprocess.run(
                    ["docker", "exec", "grodt_grodt_1", "rm", "/app/data/restore_test.txt"],
                    capture_output=True,
                    text=True
                )
                assert result.returncode == 0
                
                # Restore from backup
                result = subprocess.run(
                    ["./scripts/volume-manager.sh", "restore", "grodt_data", backup_file],
                    capture_output=True,
                    text=True
                )
                assert result.returncode == 0
                
                # Check data was restored
                result = subprocess.run(
                    ["docker", "exec", "grodt_grodt_1", "cat", "/app/data/restore_test.txt"],
                    capture_output=True,
                    text=True
                )
                assert result.returncode == 0
                assert "restore test" in result.stdout

    def test_volume_cleanup(self, docker_compose_up):
        """Test volume cleanup functionality."""
        # Run cleanup
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "cleanup"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check cleanup was performed
        backup_dir = Path("/var/lib/docker/volumes/grodt_backups")
        if backup_dir.exists():
            # Should not have very old backups
            old_backups = list(backup_dir.glob("*_old_*"))
            assert len(old_backups) == 0

    def test_volume_usage_monitoring(self, docker_compose_up):
        """Test volume usage monitoring."""
        # Check volume usage
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "usage"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for usage information
        output = result.stdout
        assert "Backup directory usage:" in output or "Volume" in output

    def test_volume_validation(self, docker_compose_up):
        """Test volume validation."""
        # Run volume validation
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "validate"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for validation results
        output = result.stdout
        assert "Volume" in output and "is accessible" in output

    def test_volume_listing(self, docker_compose_up):
        """Test volume listing functionality."""
        # List volumes
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "list"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check for volume information
        output = result.stdout
        assert "grodt_data" in output
        assert "grodt_logs" in output

    def test_volume_history(self, docker_compose_up):
        """Test volume backup history."""
        # Create a backup
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "backup", "grodt_data"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check backup history
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "history"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Should show backup history
        output = result.stdout
        assert "grodt_data_" in output

    def test_volume_monitoring_service(self, docker_compose_up):
        """Test volume monitoring service."""
        # Start volume monitoring
        result = subprocess.run(
            ["docker-compose", "-f", "docker/volume-monitor.yml", "up", "-d"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Wait for service to start
        time.sleep(10)
        
        # Check monitoring service is running
        result = subprocess.run(
            ["docker-compose", "-f", "docker/volume-monitor.yml", "ps"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Cleanup monitoring service
        subprocess.run(
            ["docker-compose", "-f", "docker/volume-monitor.yml", "down"],
            capture_output=True
        )

    def test_volume_cleanup_policies(self, docker_compose_up):
        """Test volume cleanup policies."""
        # Create temporary files
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "sh", "-c", "touch /app/logs/temp_file.tmp"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Run cleanup
        result = subprocess.run(
            ["./scripts/volume-manager.sh", "cleanup"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check temporary files were cleaned up
        result = subprocess.run(
            ["docker", "exec", "grodt_grodt_1", "ls", "/app/logs/temp_file.tmp"],
            capture_output=True,
            text=True
        )
        # File should not exist after cleanup
        assert result.returncode != 0
