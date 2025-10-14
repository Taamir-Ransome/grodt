"""
Integration tests for analytics service.

Tests the integration between analytics service and other system components.
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from grodtd.analytics.regime_performance_service import RegimePerformanceService
from grodtd.regime.service import RegimeStateService
from grodtd.regime.classifier import RegimeType
from grodtd.execution.trade_entry_service import TradeEntryService
from grodtd.connectors.robinhood import RobinhoodConnector
from grodtd.risk.manager import RiskManager, RiskLimits
from grodtd.storage.interfaces import OHLCVBar


class TestAnalyticsIntegration:
    """Test analytics service integration with other components."""

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        os.unlink(db_path)

    @pytest.fixture
    def mock_regime_service(self):
        """Create a mock regime service."""
        service = Mock(spec=RegimeStateService)
        service.get_current_regime.return_value = 'trending'
        service.get_regime_confidence.return_value = 0.85
        return service

    @pytest.fixture
    def analytics_service(self, temp_db, mock_regime_service):
        """Create analytics service for testing."""
        return RegimePerformanceService(temp_db, mock_regime_service)

    @pytest.fixture
    def mock_connector(self):
        """Create a mock Robinhood connector."""
        connector = Mock(spec=RobinhoodConnector)
        connector.get_account.return_value = {'buying_power': 10000.0}
        return connector

    @pytest.fixture
    def risk_manager(self):
        """Create risk manager for testing."""
        risk_limits = RiskLimits(
            max_position_size=1000.0,
            max_daily_loss=500.0,
            max_drawdown=0.1
        )
        return RiskManager(risk_limits, 10000.0)

    def test_regime_service_integration(self, analytics_service, mock_regime_service):
        """Test integration with regime service."""
        # Test regime accuracy tracking
        symbol = "BTC"
        predicted_regime = RegimeType.TRENDING
        actual_regime = RegimeType.TRENDING
        confidence = 0.85
        
        success = analytics_service.update_regime_accuracy(
            symbol, predicted_regime, actual_regime, confidence
        )
        
        assert success is True
        
        # Verify accuracy data was stored
        accuracy_data = analytics_service.get_regime_accuracy(symbol)
        assert len(accuracy_data) > 0
        # Check that the regime accuracy data exists
        assert predicted_regime.value in accuracy_data
        regime_data = accuracy_data[predicted_regime.value]
        assert regime_data['total_predictions'] > 0
        assert regime_data['accuracy'] >= 0.0

    def test_trade_entry_service_integration(self, temp_db, mock_connector, risk_manager):
        """Test integration with trade entry service."""
        # Create analytics service
        mock_regime_service = Mock(spec=RegimeStateService)
        analytics_service = RegimePerformanceService(temp_db, mock_regime_service)
        
        # Create trade entry service with analytics
        config = {
            'strategy': {},
            'trade_exit': {'auto_exit_on_fill': True},
            'database_url': f'sqlite:///{temp_db}'
        }
        
        trade_service = TradeEntryService(
            mock_connector, risk_manager, "BTC", config, analytics_service
        )
        
        # Test analytics summary
        summary = trade_service.get_analytics_summary()
        assert 'performance' in summary
        assert 'accuracy' in summary
        assert 'service_status' in summary
        assert summary['symbol'] == "BTC"

    def test_performance_tracking_integration(self, analytics_service):
        """Test performance tracking integration."""
        symbol = "BTC"
        
        # Simulate multiple trades with complete data
        trades = [
            {
                'pnl': 100.0, 
                'timestamp': datetime.now() - timedelta(hours=2),
                'symbol': symbol,
                'side': 'buy',
                'quantity': 1.0,
                'price': 50000.0,
                'order_id': 'trade_1'
            },
            {
                'pnl': -50.0, 
                'timestamp': datetime.now() - timedelta(hours=1),
                'symbol': symbol,
                'side': 'sell',
                'quantity': 1.0,
                'price': 49500.0,
                'order_id': 'trade_2'
            },
            {
                'pnl': 75.0, 
                'timestamp': datetime.now(),
                'symbol': symbol,
                'side': 'buy',
                'quantity': 1.0,
                'price': 50500.0,
                'order_id': 'trade_3'
            }
        ]
        
        for trade in trades:
            success = analytics_service.update_trade_performance(symbol, trade)
            assert success is True
        
        # Verify performance data
        performance = analytics_service.get_regime_performance(symbol)
        assert len(performance) > 0
        
        # Check that metrics are calculated correctly
        total_pnl = sum(trade['pnl'] for trade in trades)
        assert performance[0]['total_pnl'] == total_pnl

    def test_data_consistency_integration(self, analytics_service):
        """Test data consistency across integrated services."""
        symbol = "BTC"
        
        # Test with valid data
        trade_data = {
            'pnl': 100.0,
            'timestamp': datetime.now(),
            'symbol': symbol,
            'side': 'buy',
            'quantity': 1.0,
            'price': 50000.0,
            'order_id': 'test_order_1'
        }
        
        success = analytics_service.update_trade_performance(symbol, trade_data)
        assert success is True
        
        # Test data consistency validation
        consistency_issues = analytics_service._validate_data_consistency()
        assert len(consistency_issues) == 0

    def test_error_handling_integration(self, analytics_service):
        """Test error handling in integrated services."""
        # Test with invalid data
        invalid_trade = {
            'pnl': 'invalid',  # Invalid PnL type
            'timestamp': 'invalid_date',  # Invalid timestamp
            'symbol': None,  # Invalid symbol
        }
        
        success = analytics_service.update_trade_performance("BTC", invalid_trade)
        assert success is False  # Should handle errors gracefully
        
        # Test with invalid regime data
        success = analytics_service.update_regime_accuracy(
            "BTC", "invalid_regime", "trending", 0.5
        )
        assert success is False  # Should handle invalid regime gracefully

    def test_circuit_breaker_integration(self, analytics_service):
        """Test circuit breaker functionality in integrated services."""
        # Simulate multiple failures to trigger circuit breaker
        for _ in range(10):
            analytics_service.update_trade_performance("BTC", {'invalid': 'data'})
        
        # Circuit breaker should be open
        status = analytics_service.get_service_status()
        assert status['circuit_breaker_open'] is True
        
        # Service should be in degraded mode
        assert status['service_health'] == 'degraded'

    def test_performance_benchmarks_integration(self, analytics_service):
        """Test performance benchmarks for integrated services."""
        symbol = "BTC"
        
        # Test bulk data insertion performance
        start_time = datetime.now()
        
        # Insert 100 trades
        for i in range(100):
            trade_data = {
                'pnl': float(i),
                'timestamp': datetime.now(),
                'symbol': symbol,
                'side': 'buy' if i % 2 == 0 else 'sell',
                'quantity': 1.0,
                'price': 50000.0 + i,
                'order_id': f'test_order_{i}'
            }
            analytics_service.update_trade_performance(symbol, trade_data)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Should complete within reasonable time (less than 5 seconds)
        assert processing_time < 5.0
        
        # Test query performance
        start_time = datetime.now()
        performance = analytics_service.get_regime_performance(symbol)
        end_time = datetime.now()
        query_time = (end_time - start_time).total_seconds()
        
        # Query should be fast (less than 1 second)
        assert query_time < 1.0

    def test_concurrent_access_integration(self, analytics_service):
        """Test concurrent access to integrated services."""
        import threading
        import time
        
        results = []
        errors = []
        
        def update_performance(symbol, trade_id):
            try:
                trade_data = {
                    'pnl': float(trade_id),
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'side': 'buy',
                    'quantity': 1.0,
                    'price': 50000.0,
                    'order_id': f'concurrent_order_{trade_id}'
                }
                success = analytics_service.update_trade_performance(symbol, trade_data)
                results.append(success)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=update_performance, args=("BTC", i))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(results) == 10
        assert len(errors) == 0  # No errors should occur
        assert all(results)  # All operations should succeed

    def test_service_health_monitoring_integration(self, analytics_service):
        """Test service health monitoring in integrated services."""
        # Test initial health status
        status = analytics_service.get_service_status()
        assert status['service_health'] == 'healthy'
        assert status['circuit_breaker_open'] is False
        
        # Test with some operations
        analytics_service.update_trade_performance("BTC", {
            'pnl': 100.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC',
            'side': 'buy',
            'quantity': 1.0,
            'price': 50000.0,
            'order_id': 'health_test'
        })
        
        # Health should still be good
        status = analytics_service.get_service_status()
        assert status['service_health'] == 'healthy'