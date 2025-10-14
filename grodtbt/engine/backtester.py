"""
Vectorized backtesting engine.

This module provides a fast vectorized backtesting engine for testing
trading strategies with historical data, including fee and slippage models.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

import pandas as pd
import numpy as np


@dataclass
class BacktestConfig:
    """Backtesting configuration."""
    initial_capital: float = 10000.0
    commission_rate: float = 0.001  # 0.1% commission
    slippage_rate: float = 0.0005   # 0.05% slippage
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    benchmark_symbol: Optional[str] = None


@dataclass
class Trade:
    """Represents a completed trade."""
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    commission: float
    slippage: float
    pnl: float
    return_pct: float


@dataclass
class BacktestResult:
    """Backtesting results."""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    equity_curve: pd.DataFrame
    trades: List[Trade]
    metrics: Dict[str, float]


class VectorizedBacktester:
    """Fast vectorized backtesting engine."""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.timestamps: List[datetime] = []
        
    def run_backtest(
        self, 
        data: pd.DataFrame, 
        signals: pd.DataFrame,
        strategy_name: str = "test_strategy"
    ) -> BacktestResult:
        """
        Run vectorized backtest.
        
        Args:
            data: OHLCV data with datetime index
            signals: DataFrame with buy/sell signals
            strategy_name: Name of the strategy being tested
        
        Returns:
            Backtest results
        """
        self.logger.info(f"Starting backtest for {strategy_name}")
        
        # Initialize portfolio
        capital = self.config.initial_capital
        position = 0.0
        position_value = 0.0
        
        # Align data and signals
        aligned_data = self._align_data(data, signals)
        
        # Calculate returns
        returns = aligned_data['close'].pct_change()
        
        # Vectorized backtesting logic
        portfolio_values = []
        trade_log = []
        
        for i, (timestamp, row) in enumerate(aligned_data.iterrows()):
            current_price = row['close']
            
            # Check for signals
            if 'signal' in row and not pd.isna(row['signal']):
                signal = row['signal']
                
                if signal == 1 and position == 0:  # Buy signal
                    position = capital / current_price
                    position_value = position * current_price
                    capital = 0.0
                    
                elif signal == -1 and position > 0:  # Sell signal
                    # Calculate trade
                    trade_pnl = self._calculate_trade_pnl(
                        position, current_price, current_price, timestamp, timestamp
                    )
                    
                    trade_log.append({
                        'timestamp': timestamp,
                        'side': 'sell',
                        'quantity': position,
                        'price': current_price,
                        'pnl': trade_pnl,
                        'commission': position * current_price * self.config.commission_rate,
                        'slippage': position * current_price * self.config.slippage_rate
                    })
                    
                    capital = position * current_price - trade_pnl
                    position = 0.0
                    position_value = 0.0
            
            # Update portfolio value
            portfolio_value = capital + (position * current_price if position > 0 else 0)
            portfolio_values.append(portfolio_value)
        
        # Calculate final results
        return self._calculate_results(portfolio_values, trade_log, aligned_data)
    
    def _align_data(self, data: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
        """Align data and signals on common index."""
        # Ensure both have datetime index
        if not isinstance(data.index, pd.DatetimeIndex):
            data.index = pd.to_datetime(data.index)
        if not isinstance(signals.index, pd.DatetimeIndex):
            signals.index = pd.to_datetime(signals.index)
        
        # Align on common index
        aligned = data.join(signals, how='inner')
        return aligned
    
    def _calculate_trade_pnl(
        self, 
        quantity: float, 
        entry_price: float, 
        exit_price: float,
        entry_time: datetime,
        exit_time: datetime
    ) -> float:
        """Calculate trade PnL including fees and slippage."""
        # Base PnL
        base_pnl = quantity * (exit_price - entry_price)
        
        # Commission (both entry and exit)
        commission = quantity * (entry_price + exit_price) * self.config.commission_rate
        
        # Slippage
        slippage = quantity * (entry_price + exit_price) * self.config.slippage_rate
        
        # Net PnL
        net_pnl = base_pnl - commission - slippage
        
        return net_pnl
    
    def _calculate_results(
        self, 
        portfolio_values: List[float], 
        trade_log: List[Dict], 
        data: pd.DataFrame
    ) -> BacktestResult:
        """Calculate backtest results and metrics."""
        portfolio_series = pd.Series(portfolio_values, index=data.index)
        
        # Basic metrics
        total_return = (portfolio_series.iloc[-1] - portfolio_series.iloc[0]) / portfolio_series.iloc[0]
        
        # Annualized return
        days = (data.index[-1] - data.index[0]).days
        annualized_return = (1 + total_return) ** (365 / days) - 1
        
        # Sharpe ratio
        returns = portfolio_series.pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # Maximum drawdown
        rolling_max = portfolio_series.expanding().max()
        drawdown = (portfolio_series - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # Trade statistics
        if trade_log:
            trade_pnls = [trade['pnl'] for trade in trade_log]
            winning_trades = [pnl for pnl in trade_pnls if pnl > 0]
            losing_trades = [pnl for pnl in trade_pnls if pnl < 0]
            
            win_rate = len(winning_trades) / len(trade_pnls) if trade_pnls else 0
            avg_win = np.mean(winning_trades) if winning_trades else 0
            avg_loss = np.mean(losing_trades) if losing_trades else 0
            profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if losing_trades else float('inf')
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        # Create equity curve DataFrame
        equity_curve = pd.DataFrame({
            'timestamp': data.index,
            'portfolio_value': portfolio_values,
            'drawdown': drawdown
        })
        
        # Additional metrics
        metrics = {
            'volatility': returns.std() * np.sqrt(252),
            'skewness': returns.skew(),
            'kurtosis': returns.kurtosis(),
            'var_95': returns.quantile(0.05),
            'cvar_95': returns[returns <= returns.quantile(0.05)].mean()
        }
        
        return BacktestResult(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(trade_log),
            winning_trades=len(winning_trades) if trade_log else 0,
            losing_trades=len(losing_trades) if trade_log else 0,
            avg_win=avg_win,
            avg_loss=avg_loss,
            equity_curve=equity_curve,
            trades=[],  # TODO: Convert trade_log to Trade objects
            metrics=metrics
        )
    
    def add_fee_model(self, fee_model: str, **kwargs):
        """Add custom fee model."""
        # TODO: Implement custom fee models
        pass
    
    def add_slippage_model(self, slippage_model: str, **kwargs):
        """Add custom slippage model."""
        # TODO: Implement custom slippage models
        pass


# Factory function for creating backtester
def create_backtester(config: BacktestConfig) -> VectorizedBacktester:
    """Create a new vectorized backtester."""
    return VectorizedBacktester(config)
