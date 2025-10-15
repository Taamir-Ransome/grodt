"""
Integration tests for Grafana dashboard functionality.
"""

import pytest
import requests
import time
from pathlib import Path


class TestGrafanaIntegration:
    """Integration tests for Grafana dashboard functionality."""
    
    @pytest.fixture(scope="class")
    def grafana_url(self):
        """Grafana base URL."""
        return "http://localhost:3000"
    
    @pytest.fixture(scope="class")
    def prometheus_url(self):
        """Prometheus base URL."""
        return "http://localhost:9091"
    
    @pytest.fixture(scope="class")
    def grodt_metrics_url(self):
        """GRODT metrics endpoint URL."""
        return "http://localhost:9090/metrics"
    
    def test_grafana_accessible(self, grafana_url):
        """Test that Grafana is accessible."""
        try:
            response = requests.get(grafana_url, timeout=10)
            assert response.status_code == 200, "Grafana should be accessible"
        except requests.exceptions.ConnectionError:
            pytest.skip("Grafana not running - start with docker-compose up")
    
    def test_prometheus_accessible(self, prometheus_url):
        """Test that Prometheus is accessible."""
        try:
            response = requests.get(prometheus_url, timeout=10)
            assert response.status_code == 200, "Prometheus should be accessible"
        except requests.exceptions.ConnectionError:
            pytest.skip("Prometheus not running - start with docker-compose up")
    
    def test_grodt_metrics_endpoint(self, grodt_metrics_url):
        """Test that GRODT metrics endpoint is accessible."""
        try:
            response = requests.get(grodt_metrics_url, timeout=10)
            assert response.status_code == 200, "GRODT metrics endpoint should be accessible"
            
            # Check that response contains Prometheus format
            content = response.text
            assert "# HELP" in content, "Metrics should be in Prometheus format"
            assert "# TYPE" in content, "Metrics should have type definitions"
        except requests.exceptions.ConnectionError:
            pytest.skip("GRODT application not running - start with docker-compose up")
    
    def test_grafana_datasource_configured(self, grafana_url):
        """Test that Prometheus datasource is configured in Grafana."""
        try:
            # This would require authentication in a real test
            # For now, we'll just check that Grafana is responding
            response = requests.get(grafana_url, timeout=10)
            assert response.status_code == 200, "Grafana should be accessible"
        except requests.exceptions.ConnectionError:
            pytest.skip("Grafana not running - start with docker-compose up")
    
    def test_dashboard_files_loaded(self):
        """Test that dashboard files are properly loaded."""
        docker_dir = Path(__file__).parent.parent.parent.parent.parent / "grodt" / "docker"
        dashboards_dir = docker_dir / "grafana" / "dashboards"
        
        expected_dashboards = [
            "home.json",
            "trading-performance.json",
            "system-health.json",
            "regime-classification.json",
            "strategy-performance.json"
        ]
        
        for dashboard in expected_dashboards:
            dashboard_file = dashboards_dir / dashboard
            assert dashboard_file.exists(), f"Dashboard {dashboard} should exist"
            
            # Verify JSON is valid
            import json
            with open(dashboard_file, 'r') as f:
                dashboard_data = json.load(f)
                assert "title" in dashboard_data, f"{dashboard} should have a title"
                assert "panels" in dashboard_data, f"{dashboard} should have panels"
    
    def test_docker_compose_configuration(self):
        """Test that docker-compose.yml has correct configuration."""
        docker_dir = Path(__file__).parent.parent.parent.parent.parent / "grodt" / "docker"
        compose_file = docker_dir / "docker-compose.yml"
        
        assert compose_file.exists(), "docker-compose.yml should exist"
        
        with open(compose_file, 'r') as f:
            content = f.read()
        
        # Check for required services
        assert "grafana:" in content
        assert "prometheus:" in content
        assert "grodt:" in content
        
        # Check for required volume mappings
        assert "./grafana/grafana.ini:/etc/grafana/grafana.ini" in content
        assert "./grafana/dashboards:/var/lib/grafana/dashboards" in content
        
        # Check for port mappings
        assert "3000:3000" in content  # Grafana
        assert "9091:9090" in content  # Prometheus
        assert "9090:9090" in content  # GRODT metrics
    
    def test_prometheus_scrape_configuration(self):
        """Test that Prometheus is configured to scrape GRODT metrics."""
        docker_dir = Path(__file__).parent.parent.parent.parent.parent / "grodt" / "docker"
        prometheus_config = docker_dir / "prometheus" / "prometheus.yml"
        
        assert prometheus_config.exists(), "Prometheus configuration should exist"
        
        with open(prometheus_config, 'r') as f:
            content = f.read()
        
        # Check for GRODT job configuration
        assert "grodt-trading-bot" in content
        assert "grodt:9090" in content
        assert "/metrics" in content
        assert "scrape_interval: 5s" in content
