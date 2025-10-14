"""
Unit tests for RegimePerformanceService.

Tests cover all critical functionality including data consistency validation,
performance metrics calculation, and error handling.
"""

import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from grodtd.analytics.regime_performance_service import (
    RegimePerformanceService, 
    RegimePerformanceMetrics,
    RegimeAccuracyMetrics,
    DataConsistencyError
)
from grodtd.regime.service import RegimeType


class TestRegimePerformanceMetrics:
    """Test RegimePerformanceMetrics class."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization with default values."""
        metrics = RegimePerformanceMetrics(RegimeType.TRENDING)
        
        assert metrics.regime == RegimeType.TRENDING
        assert metrics.total_trades == 0
        assert metrics.winning_trades == 0
        assert metrics.losing_trades == 0
        assert metrics.total_pnl == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.current_drawdown == 0.0
        assert metrics.peak_value == 0.0
        assert metrics.sharpe_ratio == 0.0
        assert metrics.hit_rate == 0.0
        assert metrics.avg_win == 0.0
        assert metrics.avg_loss == 0.0
        assert metrics.profit_factor == 0.0
        assert isinstance(metrics.last_updated, datetime)
    
    def test_metrics_to_dict(self):
        """Test metrics serialization to dictionary."""
        metrics = RegimePerformanceMetrics(RegimeType.RANGING)
        metrics.total_trades = 10
        metrics.winning_trades = 6
        metrics.total_pnl = 150.0
        
        data = metrics.to_dict()
        
        assert data['regime'] == 'ranging'
        assert data['total_trades'] == 10
        assert data['winning_trades'] == 6
        assert data['total_pnl'] == 150.0
        assert 'last_updated' in data


class TestRegimeAccuracyMetrics:
    """Test RegimeAccuracyMetrics class."""
    
    def test_accuracy_metrics_initialization(self):
        """Test accuracy metrics initialization."""
        metrics = RegimeAccuracyMetrics(
            regime=RegimeType.TRENDING,
            total_predictions=100,
            correct_predictions=85,
            accuracy=0.85,
            confidence_avg=0.78,
            last_updated=datetime.now()
        )
        
        assert metrics.regime == RegimeType.TRENDING
        assert metrics.total_predictions == 100
        assert metrics.correct_predictions == 85
        assert metrics.accuracy == 0.85
        assert metrics.confidence_avg == 0.78
        assert isinstance(metrics.last_updated, datetime)
    
    def test_accuracy_metrics_to_dict(self):
        """Test accuracy metrics serialization."""
        metrics = RegimeAccuracyMetrics(
            regime=RegimeType.HIGH_VOLATILITY,
            total_predictions=50,
            correct_predictions=40,
            accuracy=0.8,
            confidence_avg=0.75,
            last_updated=datetime.now()
        )
        
        data = metrics.to_dict()
        
        assert data['regime'] == 'high_volatility'
        assert data['total_predictions'] == 50
        assert data['correct_predictions'] == 40
        assert data['accuracy'] == 0.8
        assert data['confidence_avg'] == 0.75
        assert 'last_updated' in data


class TestRegimePerformanceService:
    """Test RegimePerformanceService class."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def mock_regime_service(self):
        """Create a mock regime service."""
        mock_service = Mock()
        mock_service.get_current_regime.return_value = RegimeType.TRENDING
        mock_service.get_regime_confidence.return_value = 0.85
        return mock_service
    
    @pytest.fixture
    def analytics_service(self, temp_db, mock_regime_service):
        """Create analytics service instance for testing."""
        return RegimePerformanceService(temp_db, mock_regime_service)
    
    def test_service_initialization(self, analytics_service):
        """Test service initialization."""
        assert analytics_service.db_path is not None
        assert analytics_service.regime_service is not None
        assert analytics_service._circuit_breaker_state == "CLOSED"
        assert analytics_service._circuit_breaker_failures == 0
        assert analytics_service._backup_enabled is True
        assert analytics_service._transaction_rollback_enabled is True
    
    def test_database_schema_creation(self, temp_db, mock_regime_service):
        """Test that database schema is created correctly."""
        service = RegimePerformanceService(temp_db, mock_regime_service)
        
        # Check that tables exist
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            
            # Check regime_performance table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='regime_performance'
            """)
            assert cursor.fetchone() is not None
            
            # Check regime_accuracy table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='regime_accuracy'
            """)
            assert cursor.fetchone() is not None
            
            # Check data_consistency_log table
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='data_consistency_log'
            """)
            assert cursor.fetchone() is not None
    
    def test_update_trade_performance_success(self, analytics_service):
        """Test successful trade performance update."""
        trade_data = {
            'pnl': 150.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        result = analytics_service.update_trade_performance('BTC', trade_data)
        
        assert result is True
        
        # Check that metrics were updated
        performance = analytics_service.get_regime_performance('BTC', RegimeType.TRENDING)
        assert performance['total_trades'] == 1
        assert performance['total_pnl'] == 150.0
        assert performance['winning_trades'] == 1
        assert performance['hit_rate'] == 1.0
    
    def test_update_trade_performance_losing_trade(self, analytics_service):
        """Test trade performance update for losing trade."""
        trade_data = {
            'pnl': -75.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        result = analytics_service.update_trade_performance('BTC', trade_data)
        
        assert result is True
        
        # Check that metrics were updated
        performance = analytics_service.get_regime_performance('BTC', RegimeType.TRENDING)
        assert performance['total_trades'] == 1
        assert performance['total_pnl'] == -75.0
        assert performance['losing_trades'] == 1
        assert performance['hit_rate'] == 0.0
    
    def test_update_trade_performance_data_consistency_validation(self, analytics_service):
        """Test data consistency validation for trade data."""
        # Test missing required field
        trade_data = {
            'timestamp': datetime.now(),
            'symbol': 'BTC'
            # Missing 'pnl' field
        }
        
        result = analytics_service.update_trade_performance('BTC', trade_data)
        assert result is False
        
        # Test invalid PnL type
        trade_data = {
            'pnl': 'invalid',
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        result = analytics_service.update_trade_performance('BTC', trade_data)
        assert result is False
        
        # Test symbol mismatch
        trade_data = {
            'pnl': 150.0,
            'timestamp': datetime.now(),
            'symbol': 'ETH'  # Different from requested symbol
        }
        
        result = analytics_service.update_trade_performance('BTC', trade_data)
        assert result is False
    
    def test_update_regime_accuracy_success(self, analytics_service):
        """Test successful regime accuracy update."""
        result = analytics_service.update_regime_accuracy(
            'BTC',
            RegimeType.TRENDING,
            RegimeType.TRENDING,  # Correct prediction
            0.85
        )
        
        assert result is True
        
        # Check that accuracy metrics were updated
        accuracy = analytics_service.get_regime_accuracy('BTC', RegimeType.TRENDING)
        assert accuracy['total_predictions'] == 1
        assert accuracy['correct_predictions'] == 1
        assert accuracy['accuracy'] == 1.0
        assert accuracy['confidence_avg'] == 0.85
    
    def test_update_regime_accuracy_incorrect_prediction(self, analytics_service):
        """Test regime accuracy update for incorrect prediction."""
        result = analytics_service.update_regime_accuracy(
            'BTC',
            RegimeType.TRENDING,
            RegimeType.RANGING,  # Incorrect prediction
            0.75
        )
        
        assert result is True
        
        # Check that accuracy metrics were updated
        accuracy = analytics_service.get_regime_accuracy('BTC', RegimeType.TRENDING)
        assert accuracy['total_predictions'] == 1
        assert accuracy['correct_predictions'] == 0
        assert accuracy['accuracy'] == 0.0
        assert accuracy['confidence_avg'] == 0.75
    
    def test_circuit_breaker_functionality(self, analytics_service):
        """Test circuit breaker functionality."""
        # Initially closed
        assert analytics_service._circuit_breaker_state == "CLOSED"
        
        # Simulate multiple failures
        for _ in range(6):  # More than threshold
            analytics_service._handle_circuit_breaker_failure()
        
        # Should be open now
        assert analytics_service._circuit_breaker_state == "OPEN"
        
        # Test that operations are blocked when circuit breaker is open
        trade_data = {
            'pnl': 150.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        result = analytics_service.update_trade_performance('BTC', trade_data)
        assert result is False  # Should be blocked
    
    def test_get_regime_performance_all_regimes(self, analytics_service):
        """Test getting performance for all regimes."""
        # Add some test data
        trade_data = {
            'pnl': 100.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        # Get all regimes
        performance = analytics_service.get_regime_performance('BTC')
        
        assert isinstance(performance, dict)
        assert 'trending' in performance
    
    def test_get_regime_performance_specific_regime(self, analytics_service):
        """Test getting performance for specific regime."""
        # Add some test data
        trade_data = {
            'pnl': 100.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        # Get specific regime
        performance = analytics_service.get_regime_performance('BTC', RegimeType.TRENDING)
        
        assert isinstance(performance, dict)
        assert performance['regime'] == 'trending'
        assert performance['total_trades'] == 1
    
    def test_get_regime_accuracy_all_regimes(self, analytics_service):
        """Test getting accuracy for all regimes."""
        # Add some test data
        analytics_service.update_regime_accuracy(
            'BTC', RegimeType.TRENDING, RegimeType.TRENDING, 0.85
        )
        
        # Get all regimes
        accuracy = analytics_service.get_regime_accuracy('BTC')
        
        assert isinstance(accuracy, dict)
        assert 'trending' in accuracy
    
    def test_get_regime_accuracy_specific_regime(self, analytics_service):
        """Test getting accuracy for specific regime."""
        # Add some test data
        analytics_service.update_regime_accuracy(
            'BTC', RegimeType.TRENDING, RegimeType.TRENDING, 0.85
        )
        
        # Get specific regime
        accuracy = analytics_service.get_regime_accuracy('BTC', RegimeType.TRENDING)
        
        assert isinstance(accuracy, dict)
        assert accuracy['regime'] == 'trending'
        assert accuracy['total_predictions'] == 1
    
    def test_service_status(self, analytics_service):
        """Test getting service status."""
        status = analytics_service.get_service_status()
        
        assert 'circuit_breaker_state' in status
        assert 'circuit_breaker_failures' in status
        assert 'performance_metrics_count' in status
        assert 'accuracy_metrics_count' in status
        assert 'backup_enabled' in status
        assert 'transaction_rollback_enabled' in status
    
    def test_data_consistency_validation_comprehensive(self, analytics_service):
        """Test comprehensive data consistency validation."""
        # Test valid data
        valid_trade_data = {
            'pnl': 150.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        # Mock regime service to return a regime
        analytics_service.regime_service.get_current_regime.return_value = RegimeType.TRENDING
        
        result = analytics_service._validate_trade_data_consistency('BTC', valid_trade_data)
        assert result is True
        
        # Test invalid data - missing field
        invalid_trade_data = {
            'timestamp': datetime.now(),
            'symbol': 'BTC'
            # Missing 'pnl'
        }
        
        result = analytics_service._validate_trade_data_consistency('BTC', invalid_trade_data)
        assert result is False
        
        # Test invalid data - wrong symbol
        invalid_trade_data = {
            'pnl': 150.0,
            'timestamp': datetime.now(),
            'symbol': 'ETH'  # Different from requested
        }
        
        result = analytics_service._validate_trade_data_consistency('BTC', invalid_trade_data)
        assert result is False
        
        # Test invalid data - non-numeric PnL
        invalid_trade_data = {
            'pnl': 'invalid',
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        result = analytics_service._validate_trade_data_consistency('BTC', invalid_trade_data)
        assert result is False
    
    def test_drawdown_calculation(self, analytics_service):
        """Test drawdown calculation logic."""
        # First trade - profit
        trade_data = {
            'pnl': 100.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        # Second trade - loss
        trade_data = {
            'pnl': -50.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        performance = analytics_service.get_regime_performance('BTC', RegimeType.TRENDING)
        
        assert performance['total_pnl'] == 50.0  # 100 - 50
        assert performance['current_drawdown'] == 50.0  # Peak was 100, now at 50
        assert performance['max_drawdown'] == 50.0
    
    def test_hit_rate_calculation(self, analytics_service):
        """Test hit rate calculation."""
        # Add winning trade
        trade_data = {
            'pnl': 100.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        # Add losing trade
        trade_data = {
            'pnl': -50.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        performance = analytics_service.get_regime_performance('BTC', RegimeType.TRENDING)
        
        assert performance['total_trades'] == 2
        assert performance['winning_trades'] == 1
        assert performance['losing_trades'] == 1
        assert performance['hit_rate'] == 0.5  # 1 win out of 2 trades
    
    def test_profit_factor_calculation(self, analytics_service):
        """Test profit factor calculation."""
        # Add winning trade
        trade_data = {
            'pnl': 200.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        # Add losing trade
        trade_data = {
            'pnl': -100.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        analytics_service.update_trade_performance('BTC', trade_data)
        
        performance = analytics_service.get_regime_performance('BTC', RegimeType.TRENDING)
        
        # Profit factor = (avg_win * winning_trades) / (avg_loss * losing_trades)
        # = (200 * 1) / (100 * 1) = 2.0
        assert performance['profit_factor'] == 2.0
    
    def test_database_transaction_safety(self, temp_db, mock_regime_service):
        """Test database transaction safety."""
        service = RegimePerformanceService(temp_db, mock_regime_service)
        
        # Test that database operations are wrapped in transactions
        trade_data = {
            'pnl': 150.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        result = service.update_trade_performance('BTC', trade_data)
        assert result is True
        
        # Verify data was saved to database
        with sqlite3.connect(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM regime_performance")
            count = cursor.fetchone()[0]
            assert count > 0
    
    def test_error_handling_in_update_trade_performance(self, analytics_service):
        """Test error handling in trade performance update."""
        # Test with None regime service
        analytics_service.regime_service.get_current_regime.return_value = None
        
        trade_data = {
            'pnl': 150.0,
            'timestamp': datetime.now(),
            'symbol': 'BTC'
        }
        
        result = analytics_service.update_trade_performance('BTC', trade_data)
        assert result is False
    
    def test_error_handling_in_update_regime_accuracy(self, analytics_service):
        """Test error handling in regime accuracy update."""
        # Test with invalid regime types - should return False instead of raising
        result = analytics_service.update_regime_accuracy(
            'BTC',
            'invalid_regime',  # Should be RegimeType
            RegimeType.TRENDING,
            0.85
        )
        assert result is False  # Should fail gracefully
