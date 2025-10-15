"""
Trading metrics collector for GRODT system.

Collects comprehensive trading performance metrics including:
- PnL tracking and real-time updates
- Drawdown calculation and max drawdown
- Hit rate (winning trades / total trades)
- Sharpe ratio with configurable time windows
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from prometheus_client import Counter, Histogram, Gauge, Summary

from .metrics_collector import MetricsCollector


class TradingMetricsCollector(MetricsCollector):
    """
    Collects trading performance metrics for the GRODT system.
    
    Metrics include:
    - Real-time PnL tracking
    - Drawdown monitoring
    - Hit rate calculation
    - Sharpe ratio analysis
    """
    
    def __init__(self, db_path: str, registry: Optional[Any] = None):
        """
        Initialize trading metrics collector.
        
        Args:
            db_path: Path to SQLite database
            registry: Optional Prometheus registry
        """
        self.db_path = db_path
        super().__init__(registry)
    
    def _initialize_metrics(self) -> None:
        """Initialize trading-specific metrics."""
        
        # PnL Metrics
        self.pnl_total = self.create_gauge(
            'trading_pnl_total',
            'Total profit and loss',
            ['strategy', 'symbol']
        )
        
        self.pnl_daily = self.create_gauge(
            'trading_pnl_daily',
            'Daily profit and loss',
            ['strategy', 'symbol', 'date']
        )
        
        self.pnl_per_trade = self.create_histogram(
            'trading_pnl_per_trade',
            'Profit and loss per trade',
            ['strategy', 'symbol'],
            buckets=[-1000, -500, -100, -50, -10, 0, 10, 50, 100, 500, 1000]
        )
        
        # Drawdown Metrics
        self.drawdown_current = self.create_gauge(
            'trading_drawdown_current',
            'Current drawdown percentage',
            ['strategy', 'symbol']
        )
        
        self.drawdown_max = self.create_gauge(
            'trading_drawdown_max',
            'Maximum drawdown percentage',
            ['strategy', 'symbol']
        )
        
        self.drawdown_duration = self.create_gauge(
            'trading_drawdown_duration_seconds',
            'Current drawdown duration in seconds',
            ['strategy', 'symbol']
        )
        
        # Hit Rate Metrics
        self.trades_total = self.create_counter(
            'trading_trades_total',
            'Total number of trades',
            ['strategy', 'symbol', 'side']
        )
        
        self.trades_winning = self.create_counter(
            'trading_trades_winning',
            'Number of winning trades',
            ['strategy', 'symbol']
        )
        
        self.hit_rate = self.create_gauge(
            'trading_hit_rate',
            'Hit rate (winning trades / total trades)',
            ['strategy', 'symbol']
        )
        
        # Sharpe Ratio Metrics
        self.sharpe_ratio = self.create_gauge(
            'trading_sharpe_ratio',
            'Sharpe ratio',
            ['strategy', 'symbol', 'time_window']
        )
        
        self.returns_volatility = self.create_gauge(
            'trading_returns_volatility',
            'Returns volatility (standard deviation)',
            ['strategy', 'symbol', 'time_window']
        )
        
        self.returns_mean = self.create_gauge(
            'trading_returns_mean',
            'Mean returns',
            ['strategy', 'symbol', 'time_window']
        )
        
        # Portfolio Metrics
        self.portfolio_value = self.create_gauge(
            'trading_portfolio_value',
            'Current portfolio value',
            ['strategy']
        )
        
        self.portfolio_return = self.create_gauge(
            'trading_portfolio_return',
            'Portfolio return percentage',
            ['strategy', 'time_window']
        )
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect trading metrics from the database.
        
        Returns:
            Dictionary containing trading metrics data
        """
        try:
            # Get current portfolio data
            portfolio_data = await self._get_portfolio_data()
            
            # Get trade statistics
            trade_stats = await self._get_trade_statistics()
            
            # Calculate performance metrics
            performance_metrics = await self._calculate_performance_metrics()
            
            # Update Prometheus metrics
            await self._update_prometheus_metrics(portfolio_data, trade_stats, performance_metrics)
            
            return {
                'portfolio': portfolio_data,
                'trade_statistics': trade_stats,
                'performance': performance_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting trading metrics: {e}")
            raise
    
    async def _get_portfolio_data(self) -> Dict[str, Any]:
        """Get current portfolio data from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current positions
                cursor.execute("""
                    SELECT symbol, quantity, average_entry_price
                    FROM positions
                    WHERE quantity != 0
                """)
                positions = cursor.fetchall()
                
                # Get latest portfolio value
                cursor.execute("""
                    SELECT portfolio_value, timestamp
                    FROM equity_curve
                    ORDER BY timestamp DESC
                    LIMIT 1
                """)
                latest_value = cursor.fetchone()
                
                # Get portfolio value history for calculations
                cursor.execute("""
                    SELECT portfolio_value, timestamp
                    FROM equity_curve
                    ORDER BY timestamp DESC
                    LIMIT 100
                """)
                value_history = cursor.fetchall()
                
                return {
                    'positions': positions,
                    'current_value': latest_value[0] if latest_value else 0.0,
                    'value_timestamp': latest_value[1] if latest_value else None,
                    'value_history': value_history
                }
                
        except Exception as e:
            self.logger.error(f"Error getting portfolio data: {e}")
            return {'positions': [], 'current_value': 0.0, 'value_timestamp': None, 'value_history': []}
    
    async def _get_trade_statistics(self) -> Dict[str, Any]:
        """Get trade statistics from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get total trades
                cursor.execute("""
                    SELECT COUNT(*) as total_trades,
                           COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                           COUNT(CASE WHEN pnl < 0 THEN 1 END) as losing_trades,
                           AVG(pnl) as avg_pnl,
                           SUM(pnl) as total_pnl
                    FROM trades
                    WHERE fill_timestamp IS NOT NULL
                """)
                trade_stats = cursor.fetchone()
                
                # Get trades by symbol
                cursor.execute("""
                    SELECT symbol, 
                           COUNT(*) as total_trades,
                           COUNT(CASE WHEN pnl > 0 THEN 1 END) as winning_trades,
                           AVG(pnl) as avg_pnl,
                           SUM(pnl) as total_pnl
                    FROM trades
                    WHERE fill_timestamp IS NOT NULL
                    GROUP BY symbol
                """)
                symbol_stats = cursor.fetchall()
                
                return {
                    'total_trades': trade_stats[0] or 0,
                    'winning_trades': trade_stats[1] or 0,
                    'losing_trades': trade_stats[2] or 0,
                    'avg_pnl': trade_stats[3] or 0.0,
                    'total_pnl': trade_stats[4] or 0.0,
                    'by_symbol': symbol_stats
                }
                
        except Exception as e:
            self.logger.error(f"Error getting trade statistics: {e}")
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'avg_pnl': 0.0,
                'total_pnl': 0.0,
                'by_symbol': []
            }
    
    async def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """Calculate performance metrics like drawdown and Sharpe ratio."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get equity curve for drawdown calculation
                cursor.execute("""
                    SELECT portfolio_value, timestamp
                    FROM equity_curve
                    ORDER BY timestamp ASC
                """)
                equity_curve = cursor.fetchall()
                
                if not equity_curve:
                    return {
                        'current_drawdown': 0.0,
                        'max_drawdown': 0.0,
                        'drawdown_duration': 0,
                        'sharpe_ratio_30d': 0.0,
                        'sharpe_ratio_90d': 0.0
                    }
                
                # Calculate drawdown
                drawdown_metrics = self._calculate_drawdown(equity_curve)
                
                # Calculate Sharpe ratio for different time windows
                sharpe_metrics = await self._calculate_sharpe_ratios(equity_curve)
                
                return {
                    **drawdown_metrics,
                    **sharpe_metrics
                }
                
        except Exception as e:
            self.logger.error(f"Error calculating performance metrics: {e}")
            return {
                'current_drawdown': 0.0,
                'max_drawdown': 0.0,
                'drawdown_duration': 0,
                'sharpe_ratio_30d': 0.0,
                'sharpe_ratio_90d': 0.0
            }
    
    def _calculate_drawdown(self, equity_curve: List[Tuple[float, str]]) -> Dict[str, Any]:
        """Calculate current and maximum drawdown."""
        if not equity_curve:
            return {'current_drawdown': 0.0, 'max_drawdown': 0.0, 'drawdown_duration': 0}
        
        values = [row[0] for row in equity_curve]
        peak = values[0]
        max_drawdown = 0.0
        current_drawdown = 0.0
        drawdown_duration = 0
        in_drawdown = False
        
        for i, value in enumerate(values):
            if value > peak:
                peak = value
                if in_drawdown:
                    in_drawdown = False
                    drawdown_duration = 0
            else:
                if not in_drawdown:
                    in_drawdown = True
                    drawdown_duration = 0
                else:
                    drawdown_duration += 1
                
                drawdown = (peak - value) / peak * 100
                max_drawdown = max(max_drawdown, drawdown)
                
                if i == len(values) - 1:  # Current value
                    current_drawdown = drawdown
        
        return {
            'current_drawdown': current_drawdown,
            'max_drawdown': max_drawdown,
            'drawdown_duration': drawdown_duration
        }
    
    async def _calculate_sharpe_ratios(self, equity_curve: List[Tuple[float, str]]) -> Dict[str, Any]:
        """Calculate Sharpe ratios for different time windows."""
        if len(equity_curve) < 2:
            return {'sharpe_ratio_30d': 0.0, 'sharpe_ratio_90d': 0.0}
        
        # Calculate returns
        returns = []
        for i in range(1, len(equity_curve)):
            prev_value = equity_curve[i-1][0]
            curr_value = equity_curve[i][0]
            if prev_value > 0:
                returns.append((curr_value - prev_value) / prev_value)
        
        if not returns:
            return {'sharpe_ratio_30d': 0.0, 'sharpe_ratio_90d': 0.0}
        
        # Calculate Sharpe ratios for different windows
        sharpe_30d = self._calculate_sharpe_ratio(returns[-30:]) if len(returns) >= 30 else 0.0
        sharpe_90d = self._calculate_sharpe_ratio(returns[-90:]) if len(returns) >= 90 else 0.0
        
        return {
            'sharpe_ratio_30d': sharpe_30d,
            'sharpe_ratio_90d': sharpe_90d
        }
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio for a given set of returns."""
        if not returns or len(returns) < 2:
            return 0.0
        
        import statistics
        
        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns) if len(returns) > 1 else 0.0
        
        if std_return == 0:
            return 0.0
        
        # Assuming risk-free rate of 0 for simplicity
        return mean_return / std_return
    
    async def _update_prometheus_metrics(self, 
                                       portfolio_data: Dict[str, Any],
                                       trade_stats: Dict[str, Any],
                                       performance_metrics: Dict[str, Any]) -> None:
        """Update Prometheus metrics with collected data."""
        
        # Update portfolio metrics
        self.portfolio_value.labels(strategy='default').set(portfolio_data['current_value'])
        
        # Update PnL metrics
        self.pnl_total.labels(strategy='default', symbol='total').set(trade_stats['total_pnl'])
        
        # Update drawdown metrics
        self.drawdown_current.labels(strategy='default', symbol='total').set(
            performance_metrics['current_drawdown']
        )
        self.drawdown_max.labels(strategy='default', symbol='total').set(
            performance_metrics['max_drawdown']
        )
        
        # Update hit rate
        total_trades = trade_stats['total_trades']
        winning_trades = trade_stats['winning_trades']
        hit_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
        
        self.hit_rate.labels(strategy='default', symbol='total').set(hit_rate)
        
        # Update Sharpe ratios
        self.sharpe_ratio.labels(
            strategy='default', 
            symbol='total', 
            time_window='30d'
        ).set(performance_metrics['sharpe_ratio_30d'])
        
        self.sharpe_ratio.labels(
            strategy='default', 
            symbol='total', 
            time_window='90d'
        ).set(performance_metrics['sharpe_ratio_90d'])
        
        # Update trade counters
        self.trades_total.labels(
            strategy='default', 
            symbol='total', 
            side='all'
        )._value._value = total_trades
        
        self.trades_winning.labels(
            strategy='default', 
            symbol='total'
        )._value._value = winning_trades
