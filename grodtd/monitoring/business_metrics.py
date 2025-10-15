"""
Business metrics collector for GRODT trading system.

Collects business-specific metrics including:
- Regime classification accuracy metrics
- Strategy performance tracking per regime
- Feature store performance metrics
- Data pipeline health metrics
- Risk management metrics
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from prometheus_client import Counter, Histogram, Gauge, Summary

from .metrics_collector import MetricsCollector


class BusinessMetricsCollector(MetricsCollector):
    """
    Collects business-specific metrics for the GRODT system.
    
    Metrics include:
    - Regime classification accuracy
    - Strategy performance by regime
    - Feature store performance
    - Data pipeline health
    - Risk management metrics
    """
    
    def __init__(self, db_path: str, registry: Optional[Any] = None):
        """
        Initialize business metrics collector.
        
        Args:
            db_path: Path to SQLite database
            registry: Optional Prometheus registry
        """
        self.db_path = db_path
        super().__init__(registry)
    
    def _initialize_metrics(self) -> None:
        """Initialize business-specific metrics."""
        
        # Regime Classification Metrics
        self.regime_predictions_total = self.create_counter(
            'regime_predictions_total',
            'Total regime predictions',
            ['symbol', 'regime_type']
        )
        
        self.regime_accuracy = self.create_gauge(
            'regime_classification_accuracy',
            'Regime classification accuracy',
            ['symbol', 'regime_type', 'time_window']
        )
        
        self.regime_confidence = self.create_histogram(
            'regime_prediction_confidence',
            'Regime prediction confidence',
            ['symbol', 'regime_type'],
            buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        )
        
        self.regime_misclassifications = self.create_counter(
            'regime_misclassifications_total',
            'Total regime misclassifications',
            ['symbol', 'predicted_regime', 'actual_regime']
        )
        
        # Strategy Performance Metrics
        self.strategy_performance = self.create_gauge(
            'strategy_performance_pnl',
            'Strategy performance PnL',
            ['strategy', 'regime', 'symbol']
        )
        
        self.strategy_trades_total = self.create_counter(
            'strategy_trades_total',
            'Total strategy trades',
            ['strategy', 'regime', 'symbol']
        )
        
        self.strategy_win_rate = self.create_gauge(
            'strategy_win_rate',
            'Strategy win rate',
            ['strategy', 'regime', 'symbol']
        )
        
        self.strategy_sharpe_ratio = self.create_gauge(
            'strategy_sharpe_ratio',
            'Strategy Sharpe ratio',
            ['strategy', 'regime', 'symbol']
        )
        
        # Feature Store Metrics
        self.feature_cache_hits = self.create_counter(
            'feature_cache_hits_total',
            'Feature cache hits',
            ['feature_type', 'symbol']
        )
        
        self.feature_cache_misses = self.create_counter(
            'feature_cache_misses_total',
            'Feature cache misses',
            ['feature_type', 'symbol']
        )
        
        self.feature_computation_time = self.create_histogram(
            'feature_computation_duration_seconds',
            'Feature computation duration',
            ['feature_type', 'symbol'],
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
        )
        
        self.feature_freshness = self.create_gauge(
            'feature_freshness_seconds',
            'Feature freshness in seconds',
            ['feature_type', 'symbol']
        )
        
        # Data Pipeline Metrics
        self.data_ingestion_rate = self.create_gauge(
            'data_ingestion_rate_per_second',
            'Data ingestion rate',
            ['data_source', 'symbol']
        )
        
        self.data_quality_score = self.create_gauge(
            'data_quality_score',
            'Data quality score (0-1)',
            ['data_source', 'symbol']
        )
        
        self.data_latency_seconds = self.create_histogram(
            'data_latency_seconds',
            'Data latency from source to system',
            ['data_source', 'symbol'],
            buckets=[1, 5, 10, 30, 60, 300, 600]
        )
        
        self.data_errors_total = self.create_counter(
            'data_errors_total',
            'Total data processing errors',
            ['data_source', 'error_type']
        )
        
        # Risk Management Metrics
        self.position_size = self.create_gauge(
            'position_size',
            'Current position size',
            ['symbol', 'strategy']
        )
        
        self.risk_exposure = self.create_gauge(
            'risk_exposure_percent',
            'Risk exposure percentage',
            ['symbol', 'strategy']
        )
        
        self.stop_loss_triggers = self.create_counter(
            'stop_loss_triggers_total',
            'Total stop loss triggers',
            ['symbol', 'strategy']
        )
        
        self.risk_limits_breached = self.create_counter(
            'risk_limits_breached_total',
            'Total risk limit breaches',
            ['limit_type', 'symbol']
        )
        
        self.max_drawdown_limit = self.create_gauge(
            'max_drawdown_limit_percent',
            'Maximum drawdown limit',
            ['strategy']
        )
    
    async def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect business metrics.
        
        Returns:
            Dictionary containing business metrics data
        """
        try:
            # Collect regime metrics
            regime_metrics = await self._collect_regime_metrics()
            
            # Collect strategy metrics
            strategy_metrics = await self._collect_strategy_metrics()
            
            # Collect feature store metrics
            feature_metrics = await self._collect_feature_metrics()
            
            # Collect data pipeline metrics
            pipeline_metrics = await self._collect_pipeline_metrics()
            
            # Collect risk management metrics
            risk_metrics = await self._collect_risk_metrics()
            
            # Update Prometheus metrics
            await self._update_prometheus_metrics(
                regime_metrics, strategy_metrics, feature_metrics, 
                pipeline_metrics, risk_metrics
            )
            
            return {
                'regime': regime_metrics,
                'strategy': strategy_metrics,
                'features': feature_metrics,
                'pipeline': pipeline_metrics,
                'risk': risk_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error collecting business metrics: {e}")
            raise
    
    async def _collect_regime_metrics(self) -> Dict[str, Any]:
        """Collect regime classification metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get regime predictions and accuracy
                cursor.execute("""
                    SELECT 
                        symbol,
                        predicted_regime,
                        actual_regime,
                        confidence,
                        timestamp
                    FROM regime_predictions
                    WHERE timestamp >= datetime('now', '-7 days')
                    ORDER BY timestamp DESC
                """)
                predictions = cursor.fetchall()
                
                # Calculate accuracy metrics
                accuracy_by_regime = {}
                confidence_scores = {}
                misclassifications = {}
                
                for pred in predictions:
                    symbol, predicted, actual, confidence, timestamp = pred
                    
                    # Track predictions
                    key = f"{symbol}_{predicted}"
                    if key not in accuracy_by_regime:
                        accuracy_by_regime[key] = {'correct': 0, 'total': 0}
                    accuracy_by_regime[key]['total'] += 1
                    
                    if predicted == actual:
                        accuracy_by_regime[key]['correct'] += 1
                    else:
                        # Track misclassifications
                        misclass_key = f"{symbol}_{predicted}_{actual}"
                        misclassifications[misclass_key] = misclassifications.get(misclass_key, 0) + 1
                    
                    # Track confidence scores
                    if symbol not in confidence_scores:
                        confidence_scores[symbol] = []
                    confidence_scores[symbol].append(confidence)
                
                # Calculate accuracy percentages
                accuracy_percentages = {}
                for key, data in accuracy_by_regime.items():
                    if data['total'] > 0:
                        accuracy_percentages[key] = (data['correct'] / data['total']) * 100
                
                return {
                    'predictions_count': len(predictions),
                    'accuracy_by_regime': accuracy_percentages,
                    'confidence_scores': confidence_scores,
                    'misclassifications': misclassifications
                }
                
        except Exception as e:
            self.logger.error(f"Error collecting regime metrics: {e}")
            return {}
    
    async def _collect_strategy_metrics(self) -> Dict[str, Any]:
        """Collect strategy performance metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get strategy performance by regime
                cursor.execute("""
                    SELECT 
                        t.symbol,
                        t.regime,
                        t.strategy,
                        COUNT(*) as trade_count,
                        SUM(t.pnl) as total_pnl,
                        AVG(t.pnl) as avg_pnl,
                        COUNT(CASE WHEN t.pnl > 0 THEN 1 END) as winning_trades
                    FROM trades t
                    WHERE t.fill_timestamp >= datetime('now', '-30 days')
                    GROUP BY t.symbol, t.regime, t.strategy
                """)
                strategy_performance = cursor.fetchall()
                
                # Calculate win rates and Sharpe ratios
                strategy_metrics = {}
                for row in strategy_performance:
                    symbol, regime, strategy, trade_count, total_pnl, avg_pnl, winning_trades = row
                    
                    win_rate = (winning_trades / trade_count * 100) if trade_count > 0 else 0
                    
                    # Calculate Sharpe ratio (simplified)
                    cursor.execute("""
                        SELECT pnl FROM trades 
                        WHERE symbol = ? AND regime = ? AND strategy = ?
                        AND fill_timestamp >= datetime('now', '-30 days')
                    """, (symbol, regime, strategy))
                    pnl_values = [row[0] for row in cursor.fetchall()]
                    
                    sharpe_ratio = 0.0
                    if len(pnl_values) > 1:
                        import statistics
                        mean_pnl = statistics.mean(pnl_values)
                        std_pnl = statistics.stdev(pnl_values)
                        if std_pnl > 0:
                            sharpe_ratio = mean_pnl / std_pnl
                    
                    key = f"{strategy}_{regime}_{symbol}"
                    strategy_metrics[key] = {
                        'trade_count': trade_count,
                        'total_pnl': total_pnl,
                        'avg_pnl': avg_pnl,
                        'win_rate': win_rate,
                        'sharpe_ratio': sharpe_ratio
                    }
                
                return strategy_metrics
                
        except Exception as e:
            self.logger.error(f"Error collecting strategy metrics: {e}")
            return {}
    
    async def _collect_feature_metrics(self) -> Dict[str, Any]:
        """Collect feature store performance metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get feature cache statistics
                cursor.execute("""
                    SELECT 
                        feature_type,
                        symbol,
                        cache_hits,
                        cache_misses,
                        computation_time,
                        last_updated
                    FROM feature_cache_stats
                    WHERE last_updated >= datetime('now', '-1 day')
                """)
                cache_stats = cursor.fetchall()
                
                # Calculate cache hit rates
                cache_metrics = {}
                for row in cache_stats:
                    feature_type, symbol, hits, misses, comp_time, last_updated = row
                    
                    total_requests = hits + misses
                    hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0
                    
                    # Calculate freshness
                    last_update = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    freshness = (datetime.now() - last_update).total_seconds()
                    
                    key = f"{feature_type}_{symbol}"
                    cache_metrics[key] = {
                        'hits': hits,
                        'misses': misses,
                        'hit_rate': hit_rate,
                        'computation_time': comp_time,
                        'freshness': freshness
                    }
                
                return cache_metrics
                
        except Exception as e:
            self.logger.error(f"Error collecting feature metrics: {e}")
            return {}
    
    async def _collect_pipeline_metrics(self) -> Dict[str, Any]:
        """Collect data pipeline health metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get data ingestion rates
                cursor.execute("""
                    SELECT 
                        data_source,
                        symbol,
                        COUNT(*) as record_count,
                        MIN(timestamp) as earliest,
                        MAX(timestamp) as latest
                    FROM market_data
                    WHERE timestamp >= datetime('now', '-1 hour')
                    GROUP BY data_source, symbol
                """)
                ingestion_data = cursor.fetchall()
                
                # Calculate ingestion rates
                pipeline_metrics = {}
                for row in ingestion_data:
                    data_source, symbol, count, earliest, latest = row
                    
                    # Calculate rate (records per second)
                    if earliest and latest:
                        time_diff = (datetime.fromisoformat(latest) - datetime.fromisoformat(earliest)).total_seconds()
                        rate = count / time_diff if time_diff > 0 else 0
                    else:
                        rate = 0
                    
                    key = f"{data_source}_{symbol}"
                    pipeline_metrics[key] = {
                        'record_count': count,
                        'ingestion_rate': rate,
                        'earliest': earliest,
                        'latest': latest
                    }
                
                # Get data quality scores (simplified)
                cursor.execute("""
                    SELECT 
                        data_source,
                        symbol,
                        AVG(quality_score) as avg_quality
                    FROM data_quality
                    WHERE timestamp >= datetime('now', '-1 day')
                    GROUP BY data_source, symbol
                """)
                quality_data = cursor.fetchall()
                
                for row in quality_data:
                    data_source, symbol, quality = row
                    key = f"{data_source}_{symbol}"
                    if key not in pipeline_metrics:
                        pipeline_metrics[key] = {}
                    pipeline_metrics[key]['quality_score'] = quality or 0.0
                
                return pipeline_metrics
                
        except Exception as e:
            self.logger.error(f"Error collecting pipeline metrics: {e}")
            return {}
    
    async def _collect_risk_metrics(self) -> Dict[str, Any]:
        """Collect risk management metrics."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get current positions and risk exposure
                cursor.execute("""
                    SELECT 
                        symbol,
                        strategy,
                        quantity,
                        average_entry_price,
                        current_price,
                        (quantity * current_price) as position_value
                    FROM positions p
                    JOIN (
                        SELECT symbol, price as current_price
                        FROM market_data
                        WHERE timestamp = (
                            SELECT MAX(timestamp) FROM market_data WHERE symbol = p.symbol
                        )
                    ) md ON p.symbol = md.symbol
                    WHERE quantity != 0
                """)
                positions = cursor.fetchall()
                
                # Get risk limits and breaches
                cursor.execute("""
                    SELECT 
                        limit_type,
                        symbol,
                        COUNT(*) as breach_count
                    FROM risk_breaches
                    WHERE timestamp >= datetime('now', '-7 days')
                    GROUP BY limit_type, symbol
                """)
                risk_breaches = cursor.fetchall()
                
                # Get stop loss triggers
                cursor.execute("""
                    SELECT 
                        symbol,
                        strategy,
                        COUNT(*) as trigger_count
                    FROM stop_loss_triggers
                    WHERE timestamp >= datetime('now', '-7 days')
                    GROUP BY symbol, strategy
                """)
                stop_loss_triggers = cursor.fetchall()
                
                # Calculate risk metrics
                risk_metrics = {
                    'positions': positions,
                    'breaches': dict(risk_breaches),
                    'stop_loss_triggers': dict(stop_loss_triggers),
                    'total_exposure': sum(row[5] for row in positions if row[5])
                }
                
                return risk_metrics
                
        except Exception as e:
            self.logger.error(f"Error collecting risk metrics: {e}")
            return {}
    
    async def _update_prometheus_metrics(self,
                                       regime_metrics: Dict[str, Any],
                                       strategy_metrics: Dict[str, Any],
                                       feature_metrics: Dict[str, Any],
                                       pipeline_metrics: Dict[str, Any],
                                       risk_metrics: Dict[str, Any]) -> None:
        """Update Prometheus metrics with collected data."""
        
        # Update regime metrics
        if 'accuracy_by_regime' in regime_metrics:
            for key, accuracy in regime_metrics['accuracy_by_regime'].items():
                parts = key.split('_')
                if len(parts) >= 2:
                    symbol = parts[0]
                    regime = parts[1]
                    self.regime_accuracy.labels(
                        symbol=symbol,
                        regime_type=regime,
                        time_window='7d'
                    ).set(accuracy)
        
        # Update strategy metrics
        for key, metrics in strategy_metrics.items():
            parts = key.split('_')
            if len(parts) >= 3:
                strategy = parts[0]
                regime = parts[1]
                symbol = parts[2]
                
                self.strategy_performance.labels(
                    strategy=strategy,
                    regime=regime,
                    symbol=symbol
                ).set(metrics.get('total_pnl', 0))
                
                self.strategy_win_rate.labels(
                    strategy=strategy,
                    regime=regime,
                    symbol=symbol
                ).set(metrics.get('win_rate', 0))
                
                self.strategy_sharpe_ratio.labels(
                    strategy=strategy,
                    regime=regime,
                    symbol=symbol
                ).set(metrics.get('sharpe_ratio', 0))
        
        # Update feature metrics
        for key, metrics in feature_metrics.items():
            parts = key.split('_')
            if len(parts) >= 2:
                feature_type = parts[0]
                symbol = parts[1]
                
                self.feature_cache_hits.labels(
                    feature_type=feature_type,
                    symbol=symbol
                )._value._value = metrics.get('hits', 0)
                
                self.feature_cache_misses.labels(
                    feature_type=feature_type,
                    symbol=symbol
                )._value._value = metrics.get('misses', 0)
                
                self.feature_freshness.labels(
                    feature_type=feature_type,
                    symbol=symbol
                ).set(metrics.get('freshness', 0))
        
        # Update pipeline metrics
        for key, metrics in pipeline_metrics.items():
            parts = key.split('_')
            if len(parts) >= 2:
                data_source = parts[0]
                symbol = parts[1]
                
                self.data_ingestion_rate.labels(
                    data_source=data_source,
                    symbol=symbol
                ).set(metrics.get('ingestion_rate', 0))
                
                self.data_quality_score.labels(
                    data_source=data_source,
                    symbol=symbol
                ).set(metrics.get('quality_score', 0))
        
        # Update risk metrics
        if 'positions' in risk_metrics:
            for position in risk_metrics['positions']:
                symbol, strategy, quantity, entry_price, current_price, position_value = position
                
                self.position_size.labels(
                    symbol=symbol,
                    strategy=strategy
                ).set(quantity)
                
                # Calculate risk exposure as percentage of portfolio
                total_exposure = risk_metrics.get('total_exposure', 1)
                exposure_percent = (position_value / total_exposure * 100) if total_exposure > 0 else 0
                
                self.risk_exposure.labels(
                    symbol=symbol,
                    strategy=strategy
                ).set(exposure_percent)
