"""
Unit tests for trading metrics collector.
"""

import pytest
import asyncio
import sqlite3
import tempfile
import os
from unittest.mock import Mock, patch
from prometheus_client import CollectorRegistry

from grodtd.monitoring.trading_metrics import TradingMetricsCollector


class TestTradingMetricsCollector:
    """Test cases for TradingMetricsCollector."""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        # Create test database with required tables
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Create trades table
            cursor.execute("""
                CREATE TABLE trades (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    side TEXT,
                    quantity REAL,
                    price REAL,
                    pnl REAL,
                    fill_timestamp TEXT,
                    strategy TEXT,
                    regime TEXT
                )
            """)
            
            # Create positions table
            cursor.execute("""
                CREATE TABLE positions (
                    symbol TEXT PRIMARY KEY,
                    quantity REAL,
                    average_entry_price REAL
                )
            """)
            
            # Create equity_curve table
            cursor.execute("""
                CREATE TABLE equity_curve (
                    timestamp TEXT,
                    portfolio_value REAL
                )
            """)
            
            # Insert test data
            cursor.execute("""
                INSERT INTO trades (symbol, side, quantity, price, pnl, fill_timestamp, strategy, regime)
                VALUES 
                    ('BTC', 'buy', 1.0, 50000.0, 100.0, '2024-01-01T10:00:00Z', 'trend', 'trending'),
                    ('BTC', 'sell', 1.0, 51000.0, 100.0, '2024-01-01T11:00:00Z', 'trend', 'trending'),
                    ('ETH', 'buy', 10.0, 3000.0, -50.0, '2024-01-01T12:00:00Z', 'trend', 'ranging')
            """)
            
            cursor.execute("""
                INSERT INTO positions (symbol, quantity, average_entry_price)
                VALUES 
                    ('BTC', 0.0, 0.0),
                    ('ETH', 10.0, 3000.0)
            """)
            
            cursor.execute("""
                INSERT INTO equity_curve (timestamp, portfolio_value)
                VALUES 
                    ('2024-01-01T09:00:00Z', 10000.0),
                    ('2024-01-01T10:00:00Z', 10100.0),
                    ('2024-01-01T11:00:00Z', 10200.0),
                    ('2024-01-01T12:00:00Z', 10150.0)
            """)
            
            conn.commit()
        
        yield db_path
        
        # Cleanup
        os.unlink(db_path)
    
    def test_initialization(self, temp_db):
        """Test trading metrics collector initialization."""
        collector = TradingMetricsCollector(temp_db)
        
        assert collector.db_path == temp_db
        assert collector.registry is not None
        
        # Check that metrics were initialized
        assert hasattr(collector, 'pnl_total')
        assert hasattr(collector, 'drawdown_current')
        assert hasattr(collector, 'hit_rate')
        assert hasattr(collector, 'sharpe_ratio')
    
    @pytest.mark.asyncio
    async def test_collect_metrics(self, temp_db):
        """Test metrics collection."""
        collector = TradingMetricsCollector(temp_db)
        
        result = await collector.collect_metrics()
        
        assert 'portfolio' in result
        assert 'trade_statistics' in result
        assert 'performance' in result
        assert 'timestamp' in result
        
        # Check portfolio data
        portfolio = result['portfolio']
        assert 'positions' in portfolio
        assert 'current_value' in portfolio
        assert 'value_history' in portfolio
        
        # Check trade statistics
        trade_stats = result['trade_statistics']
        assert 'total_trades' in trade_stats
        assert 'winning_trades' in trade_stats
        assert 'total_pnl' in trade_stats
        
        # Check performance metrics
        performance = result['performance']
        assert 'current_drawdown' in performance
        assert 'max_drawdown' in performance
        assert 'sharpe_ratio_30d' in performance
    
    @pytest.mark.asyncio
    async def test_get_portfolio_data(self, temp_db):
        """Test portfolio data collection."""
        collector = TradingMetricsCollector(temp_db)
        
        portfolio_data = await collector._get_portfolio_data()
        
        assert 'positions' in portfolio_data
        assert 'current_value' in portfolio_data
        assert 'value_timestamp' in portfolio_data
        assert 'value_history' in portfolio_data
        
        # Check that positions are retrieved
        assert len(portfolio_data['positions']) >= 0
        assert portfolio_data['current_value'] >= 0
    
    @pytest.mark.asyncio
    async def test_get_trade_statistics(self, temp_db):
        """Test trade statistics collection."""
        collector = TradingMetricsCollector(temp_db)
        
        trade_stats = await collector._get_trade_statistics()
        
        assert 'total_trades' in trade_stats
        assert 'winning_trades' in trade_stats
        assert 'losing_trades' in trade_stats
        assert 'avg_pnl' in trade_stats
        assert 'total_pnl' in trade_stats
        assert 'by_symbol' in trade_stats
        
        # With test data, we should have 3 trades
        assert trade_stats['total_trades'] == 3
        assert trade_stats['winning_trades'] == 2  # 2 positive PnL trades
        assert trade_stats['losing_trades'] == 1   # 1 negative PnL trade
    
    @pytest.mark.asyncio
    async def test_calculate_performance_metrics(self, temp_db):
        """Test performance metrics calculation."""
        collector = TradingMetricsCollector(temp_db)
        
        performance_metrics = await collector._calculate_performance_metrics()
        
        assert 'current_drawdown' in performance_metrics
        assert 'max_drawdown' in performance_metrics
        assert 'drawdown_duration' in performance_metrics
        assert 'sharpe_ratio_30d' in performance_metrics
        assert 'sharpe_ratio_90d' in performance_metrics
        
        # All values should be numeric
        assert isinstance(performance_metrics['current_drawdown'], (int, float))
        assert isinstance(performance_metrics['max_drawdown'], (int, float))
        assert isinstance(performance_metrics['sharpe_ratio_30d'], (int, float))
    
    def test_calculate_drawdown(self, temp_db):
        """Test drawdown calculation."""
        collector = TradingMetricsCollector(temp_db)
        
        # Test with sample equity curve
        equity_curve = [
            (10000.0, '2024-01-01T09:00:00Z'),
            (10100.0, '2024-01-01T10:00:00Z'),
            (10200.0, '2024-01-01T11:00:00Z'),
            (10150.0, '2024-01-01T12:00:00Z')
        ]
        
        drawdown_metrics = collector._calculate_drawdown(equity_curve)
        
        assert 'current_drawdown' in drawdown_metrics
        assert 'max_drawdown' in drawdown_metrics
        assert 'drawdown_duration' in drawdown_metrics
        
        # With the test data, current drawdown should be 0.49% (10200 - 10150) / 10200
        assert drawdown_metrics['current_drawdown'] == pytest.approx(0.49, rel=0.1)
    
    def test_calculate_sharpe_ratio(self, temp_db):
        """Test Sharpe ratio calculation."""
        collector = TradingMetricsCollector(temp_db)
        
        # Test with sample returns
        returns = [0.01, 0.02, -0.01, 0.015, 0.005]
        sharpe_ratio = collector._calculate_sharpe_ratio(returns)
        
        assert isinstance(sharpe_ratio, (int, float))
        assert sharpe_ratio >= 0  # Should be positive for this test data
    
    @pytest.mark.asyncio
    async def test_update_prometheus_metrics(self, temp_db):
        """Test Prometheus metrics update."""
        collector = TradingMetricsCollector(temp_db)
        
        # Mock portfolio and trade data
        portfolio_data = {
            'current_value': 10000.0,
            'positions': [],
            'value_history': []
        }
        
        trade_stats = {
            'total_trades': 10,
            'winning_trades': 6,
            'total_pnl': 500.0
        }
        
        performance_metrics = {
            'current_drawdown': 2.5,
            'max_drawdown': 5.0,
            'sharpe_ratio_30d': 1.2,
            'sharpe_ratio_90d': 1.0
        }
        
        # This should not raise an exception
        await collector._update_prometheus_metrics(
            portfolio_data, trade_stats, performance_metrics
        )
        
        # Check that metrics were set
        assert collector.portfolio_value.labels(strategy='default')._value._value == 10000.0
        assert collector.pnl_total.labels(strategy='default', symbol='total')._value._value == 500.0
    
    @pytest.mark.asyncio
    async def test_collect_with_empty_database(self):
        """Test collection with empty database."""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            # Create empty database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY)")
                cursor.execute("CREATE TABLE positions (symbol TEXT PRIMARY KEY)")
                cursor.execute("CREATE TABLE equity_curve (timestamp TEXT)")
                conn.commit()
            
            collector = TradingMetricsCollector(db_path)
            result = await collector.collect_metrics()
            
            # Should not raise an exception
            assert 'portfolio' in result
            assert 'trade_statistics' in result
            assert 'performance' in result
            
        finally:
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_collect_with_database_error(self, temp_db):
        """Test collection with database error."""
        collector = TradingMetricsCollector(temp_db)
        
        # Mock database connection to raise an exception
        with patch('sqlite3.connect') as mock_connect:
            mock_connect.side_effect = Exception("Database error")
            
            result = await collector.collect_metrics()
            
            # Should handle error gracefully
            assert 'portfolio' in result
            assert result['portfolio']['current_value'] == 0.0
