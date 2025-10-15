"""
Unit tests for Grafana dashboard configuration.
"""

import json
import os
import pytest
from pathlib import Path


class TestGrafanaDashboards:
    """Test Grafana dashboard configuration and JSON validity."""
    
    def setup_method(self):
        """Setup test environment."""
        self.docker_dir = Path(__file__).parent.parent.parent.parent / "docker"
        self.grafana_dir = self.docker_dir / "grafana"
        self.dashboards_dir = self.grafana_dir / "dashboards"
    
    def test_grafana_config_exists(self):
        """Test that Grafana configuration file exists."""
        config_file = self.grafana_dir / "grafana.ini"
        assert config_file.exists(), "Grafana configuration file should exist"
    
    def test_datasource_config_exists(self):
        """Test that Prometheus datasource configuration exists."""
        datasource_file = self.grafana_dir / "datasources" / "prometheus.yml"
        assert datasource_file.exists(), "Prometheus datasource configuration should exist"
    
    def test_dashboard_files_exist(self):
        """Test that all dashboard files exist."""
        expected_dashboards = [
            "home.json",
            "trading-performance.json",
            "system-health.json",
            "regime-classification.json",
            "strategy-performance.json"
        ]
        
        for dashboard in expected_dashboards:
            dashboard_file = self.dashboards_dir / dashboard
            assert dashboard_file.exists(), f"Dashboard {dashboard} should exist"
    
    def test_dashboard_json_valid(self):
        """Test that all dashboard JSON files are valid."""
        dashboard_files = [
            "home.json",
            "trading-performance.json",
            "system-health.json",
            "regime-classification.json",
            "strategy-performance.json"
        ]
        
        for dashboard_file in dashboard_files:
            file_path = self.dashboards_dir / dashboard_file
            with open(file_path, 'r') as f:
                dashboard_data = json.load(f)
            
            # Check required fields
            assert "title" in dashboard_data, f"{dashboard_file} should have a title"
            assert "panels" in dashboard_data, f"{dashboard_file} should have panels"
            assert "uid" in dashboard_data, f"{dashboard_file} should have a uid"
    
    def test_dashboard_panels_have_datasource(self):
        """Test that all dashboard panels have Prometheus datasource."""
        dashboard_files = [
            "trading-performance.json",
            "system-health.json",
            "regime-classification.json",
            "strategy-performance.json"
        ]
        
        for dashboard_file in dashboard_files:
            file_path = self.dashboards_dir / dashboard_file
            with open(file_path, 'r') as f:
                dashboard_data = json.load(f)
            
            for panel in dashboard_data.get("panels", []):
                assert panel.get("datasource") == "Prometheus", \
                    f"Panel in {dashboard_file} should use Prometheus datasource"
    
    def test_dashboard_refresh_intervals(self):
        """Test that dashboards have appropriate refresh intervals."""
        dashboard_files = [
            "home.json",
            "trading-performance.json",
            "system-health.json",
            "regime-classification.json",
            "strategy-performance.json"
        ]
        
        for dashboard_file in dashboard_files:
            file_path = self.dashboards_dir / dashboard_file
            with open(file_path, 'r') as f:
                dashboard_data = json.load(f)
            
            refresh = dashboard_data.get("refresh", "")
            assert refresh in ["5s", "10s", "30s", "1m"], \
                f"{dashboard_file} should have appropriate refresh interval"
    
    def test_dashboard_tags(self):
        """Test that dashboards have appropriate tags."""
        expected_tags = {
            "home.json": ["overview", "home"],
            "trading-performance.json": ["trading", "performance"],
            "system-health.json": ["system", "health"],
            "regime-classification.json": ["regime", "classification"],
            "strategy-performance.json": ["strategy", "performance"]
        }
        
        for dashboard_file, expected_tag_list in expected_tags.items():
            file_path = self.dashboards_dir / dashboard_file
            with open(file_path, 'r') as f:
                dashboard_data = json.load(f)
            
            tags = dashboard_data.get("tags", [])
            for expected_tag in expected_tag_list:
                assert expected_tag in tags, \
                    f"{dashboard_file} should have tag '{expected_tag}'"
    
    def test_docker_compose_volumes(self):
        """Test that docker-compose.yml has correct volume mappings."""
        compose_file = self.docker_dir / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml should exist"
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Check for required volume mappings
        assert "./grafana/grafana.ini:/etc/grafana/grafana.ini" in content
        assert "./grafana/dashboards:/var/lib/grafana/dashboards" in content
        assert "./grafana/datasources:/etc/grafana/provisioning/datasources" in content
        assert "./grafana/dashboards/dashboard.yml:/etc/grafana/provisioning/dashboards/dashboard.yml" in content
    
    def test_prometheus_config_exists(self):
        """Test that Prometheus configuration exists."""
        prometheus_config = self.docker_dir / "prometheus" / "prometheus.yml"
        assert prometheus_config.exists(), "Prometheus configuration should exist"
        
        with open(prometheus_config, 'r') as f:
            content = f.read()
        
        # Check for GRODT job configuration
        assert "grodt-trading-bot" in content
        assert "grodt:9090" in content
        assert "/metrics" in content
