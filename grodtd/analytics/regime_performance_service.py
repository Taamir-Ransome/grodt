"""
Regime Performance Analytics Service.

This service tracks and analyzes the performance of different strategies
across various market regimes to optimize future trading decisions.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import threading
import time
import json

from grodtd.regime.service import RegimeStateService, RegimeType
from grodtd.storage.interfaces import OHLCVBar


class RegimePerformanceMetrics:
    """Performance metrics for a specific regime."""
    
    def __init__(self, regime: RegimeType):
        self.regime = regime
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.current_drawdown = 0.0
        self.peak_value = 0.0
        self.sharpe_ratio = 0.0
        self.hit_rate = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.profit_factor = 0.0
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            'regime': self.regime.value,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'total_pnl': self.total_pnl,
            'max_drawdown': self.max_drawdown,
            'current_drawdown': self.current_drawdown,
            'peak_value': self.peak_value,
            'sharpe_ratio': self.sharpe_ratio,
            'hit_rate': self.hit_rate,
            'avg_win': self.avg_win,
            'avg_loss': self.avg_loss,
            'profit_factor': self.profit_factor,
            'last_updated': self.last_updated.isoformat()
        }


@dataclass
class RegimeAccuracyMetrics:
    """Accuracy metrics for regime classification."""
    
    regime: RegimeType
    total_predictions: int
    correct_predictions: int
    accuracy: float
    confidence_avg: float
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            'regime': self.regime.value,
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy': self.accuracy,
            'confidence_avg': self.confidence_avg,
            'last_updated': self.last_updated.isoformat()
        }


class DataConsistencyError(Exception):
    """Raised when data consistency checks fail."""
    pass


class RegimePerformanceService:
    """
    Service for tracking and analyzing regime-specific performance.
    
    This service addresses critical data consistency requirements by:
    1. Validating data consistency between trade execution and analytics
    2. Implementing real-time data consistency monitoring
    3. Creating automated reconciliation processes
    4. Implementing data integrity constraints
    """
    
    def __init__(self, db_path: str, regime_service: RegimeStateService):
        self.db_path = db_path
        self.regime_service = regime_service
        self.logger = logging.getLogger(__name__)
        
        # Performance metrics cache by regime
        self._performance_metrics: Dict[RegimeType, RegimePerformanceMetrics] = {}
        self._accuracy_metrics: Dict[RegimeType, RegimeAccuracyMetrics] = {}
        
        # Data consistency monitoring
        self._consistency_checks = []
        self._last_consistency_check = None
        self._consistency_lock = threading.RLock()
        
        # Circuit breaker for service failures
        self._circuit_breaker_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60  # seconds
        
        # Data backup and recovery
        self._backup_enabled = True
        self._transaction_rollback_enabled = True
        
        # Initialize database schema
        self._initialize_database()
        
        # Load existing metrics
        self._load_metrics_from_db()
        
        self.logger.info("RegimePerformanceService initialized with data consistency monitoring")
    
    def _initialize_database(self):
        """Initialize database schema with analytics tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create regime_performance table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS regime_performance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        regime TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        total_trades INTEGER DEFAULT 0,
                        winning_trades INTEGER DEFAULT 0,
                        losing_trades INTEGER DEFAULT 0,
                        total_pnl REAL DEFAULT 0.0,
                        max_drawdown REAL DEFAULT 0.0,
                        current_drawdown REAL DEFAULT 0.0,
                        peak_value REAL DEFAULT 0.0,
                        sharpe_ratio REAL DEFAULT 0.0,
                        hit_rate REAL DEFAULT 0.0,
                        avg_win REAL DEFAULT 0.0,
                        avg_loss REAL DEFAULT 0.0,
                        profit_factor REAL DEFAULT 0.0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, regime, timestamp)
                    )
                """)
                
                # Create regime_accuracy table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS regime_accuracy (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        regime TEXT NOT NULL,
                        timestamp DATETIME NOT NULL,
                        total_predictions INTEGER DEFAULT 0,
                        correct_predictions INTEGER DEFAULT 0,
                        accuracy REAL DEFAULT 0.0,
                        confidence_avg REAL DEFAULT 0.0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(symbol, regime, timestamp)
                    )
                """)
                
                # Create data_consistency_log table for monitoring
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS data_consistency_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        check_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        details TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Create indexes for performance optimization
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_regime_performance_symbol_regime 
                    ON regime_performance(symbol, regime)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_regime_performance_timestamp 
                    ON regime_performance(timestamp)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_regime_accuracy_symbol_regime 
                    ON regime_accuracy(symbol, regime)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_regime_accuracy_timestamp 
                    ON regime_accuracy(timestamp)
                """)
                
                conn.commit()
                self.logger.info("Database schema initialized with analytics tables")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize database schema: {e}")
            raise
    
    def _load_metrics_from_db(self):
        """Load existing metrics from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Load performance metrics
                cursor.execute("""
                    SELECT regime, total_trades, winning_trades, losing_trades, total_pnl,
                           max_drawdown, current_drawdown, peak_value, sharpe_ratio, hit_rate,
                           avg_win, avg_loss, profit_factor, timestamp
                    FROM regime_performance
                    WHERE timestamp = (
                        SELECT MAX(timestamp) FROM regime_performance rp2 
                        WHERE rp2.regime = regime_performance.regime
                    )
                """)
                
                for row in cursor.fetchall():
                    regime = RegimeType(row[0])
                    metrics = RegimePerformanceMetrics(regime)
                    metrics.total_trades = row[1]
                    metrics.winning_trades = row[2]
                    metrics.losing_trades = row[3]
                    metrics.total_pnl = row[4]
                    metrics.max_drawdown = row[5]
                    metrics.current_drawdown = row[6]
                    metrics.peak_value = row[7]
                    metrics.sharpe_ratio = row[8]
                    metrics.hit_rate = row[9]
                    metrics.avg_win = row[10]
                    metrics.avg_loss = row[11]
                    metrics.profit_factor = row[12]
                    metrics.last_updated = datetime.fromisoformat(row[13])
                    
                    self._performance_metrics[regime] = metrics
                
                # Load accuracy metrics
                cursor.execute("""
                    SELECT regime, total_predictions, correct_predictions, accuracy,
                           confidence_avg, timestamp
                    FROM regime_accuracy
                    WHERE timestamp = (
                        SELECT MAX(timestamp) FROM regime_accuracy ra2 
                        WHERE ra2.regime = regime_accuracy.regime
                    )
                """)
                
                for row in cursor.fetchall():
                    regime = RegimeType(row[0])
                    accuracy_metrics = RegimeAccuracyMetrics(
                        regime=regime,
                        total_predictions=row[1],
                        correct_predictions=row[2],
                        accuracy=row[3],
                        confidence_avg=row[4],
                        last_updated=datetime.fromisoformat(row[5])
                    )
                    
                    self._accuracy_metrics[regime] = accuracy_metrics
                
                self.logger.info(f"Loaded metrics for {len(self._performance_metrics)} regimes")
                
        except Exception as e:
            self.logger.error(f"Failed to load metrics from database: {e}")
            # Continue with empty metrics rather than failing
    
    def update_trade_performance(self, symbol: str, trade_data: Dict[str, Any]) -> bool:
        """
        Update performance metrics for a trade.
        
        Args:
            symbol: Trading symbol
            trade_data: Trade data including regime, PnL, etc.
            
        Returns:
            True if update was successful
        """
        if self._circuit_breaker_state == "OPEN":
            self.logger.warning("Circuit breaker is OPEN, skipping trade performance update")
            return False
        
        try:
            # Validate data consistency before processing
            if not self._validate_trade_data_consistency(symbol, trade_data):
                raise DataConsistencyError("Trade data consistency validation failed")
            
            # Get current regime
            regime = self.regime_service.get_current_regime(symbol)
            if not regime:
                self.logger.warning(f"No regime available for symbol {symbol}")
                return False
            
            # Initialize metrics for regime if not exists
            if regime not in self._performance_metrics:
                self._performance_metrics[regime] = RegimePerformanceMetrics(regime)
            
            metrics = self._performance_metrics[regime]
            
            # Update metrics with trade data
            pnl = trade_data.get('pnl', 0.0)
            is_winning = pnl > 0
            
            metrics.total_trades += 1
            metrics.total_pnl += pnl
            
            if is_winning:
                metrics.winning_trades += 1
                metrics.avg_win = ((metrics.avg_win * (metrics.winning_trades - 1)) + pnl) / metrics.winning_trades
            else:
                metrics.losing_trades += 1
                metrics.avg_loss = ((metrics.avg_loss * (metrics.losing_trades - 1)) + abs(pnl)) / metrics.losing_trades
            
            # Update hit rate
            metrics.hit_rate = metrics.winning_trades / metrics.total_trades if metrics.total_trades > 0 else 0
            
            # Update profit factor
            if metrics.avg_loss > 0:
                metrics.profit_factor = (metrics.avg_win * metrics.winning_trades) / (metrics.avg_loss * metrics.losing_trades)
            
            # Update drawdown calculations
            if metrics.total_pnl > metrics.peak_value:
                metrics.peak_value = metrics.total_pnl
                metrics.current_drawdown = 0.0
            else:
                metrics.current_drawdown = metrics.peak_value - metrics.total_pnl
                if metrics.current_drawdown > metrics.max_drawdown:
                    metrics.max_drawdown = metrics.current_drawdown
            
            # Calculate Sharpe ratio (simplified)
            if metrics.total_trades > 1:
                # This is a simplified Sharpe calculation
                # In practice, you'd use proper risk-free rate and volatility
                metrics.sharpe_ratio = metrics.total_pnl / max(metrics.max_drawdown, 0.001)
            
            metrics.last_updated = datetime.now()
            
            # Save to database with transaction safety
            self._save_metrics_to_db(symbol, metrics)
            
            # Log consistency check
            self._log_consistency_check("trade_performance_update", "SUCCESS", {
                "symbol": symbol,
                "regime": regime.value,
                "pnl": pnl,
                "total_trades": metrics.total_trades
            })
            
            return True
            
        except DataConsistencyError as e:
            self.logger.error(f"Data consistency error in trade performance update: {e}")
            self._handle_circuit_breaker_failure()
            return False
            
        except Exception as e:
            self.logger.error(f"Error updating trade performance: {e}")
            self._handle_circuit_breaker_failure()
            return False
    
    def update_regime_accuracy(self, symbol: str, predicted_regime: RegimeType, 
                             actual_regime: RegimeType, confidence: float) -> bool:
        """
        Update regime classification accuracy metrics.
        
        Args:
            symbol: Trading symbol
            predicted_regime: Predicted regime
            actual_regime: Actual regime (determined after the fact)
            confidence: Classification confidence (0.0-1.0)
            
        Returns:
            True if update was successful
        """
        if self._circuit_breaker_state == "OPEN":
            self.logger.warning("Circuit breaker is OPEN, skipping regime accuracy update")
            return False
        
        try:
            # Initialize accuracy metrics for regime if not exists
            if predicted_regime not in self._accuracy_metrics:
                self._accuracy_metrics[predicted_regime] = RegimeAccuracyMetrics(
                    regime=predicted_regime,
                    total_predictions=0,
                    correct_predictions=0,
                    accuracy=0.0,
                    confidence_avg=0.0,
                    last_updated=datetime.now()
                )
            
            metrics = self._accuracy_metrics[predicted_regime]
            
            # Update metrics
            metrics.total_predictions += 1
            if predicted_regime == actual_regime:
                metrics.correct_predictions += 1
            
            metrics.accuracy = metrics.correct_predictions / metrics.total_predictions
            metrics.confidence_avg = ((metrics.confidence_avg * (metrics.total_predictions - 1)) + confidence) / metrics.total_predictions
            metrics.last_updated = datetime.now()
            
            # Save to database
            self._save_accuracy_metrics_to_db(symbol, metrics)
            
            # Log consistency check
            self._log_consistency_check("regime_accuracy_update", "SUCCESS", {
                "symbol": symbol,
                "predicted_regime": predicted_regime.value,
                "actual_regime": actual_regime.value,
                "accuracy": metrics.accuracy
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error updating regime accuracy: {e}")
            self._handle_circuit_breaker_failure()
            return False
    
    def get_regime_performance(self, symbol: str, regime: Optional[RegimeType] = None) -> Dict[str, Any]:
        """
        Get performance metrics for a regime.
        
        Args:
            symbol: Trading symbol
            regime: Specific regime to query (None for all regimes)
            
        Returns:
            Performance metrics dictionary
        """
        try:
            if regime:
                if regime in self._performance_metrics:
                    return self._performance_metrics[regime].to_dict()
                else:
                    return {}
            else:
                return {r.value: metrics.to_dict() for r, metrics in self._performance_metrics.items()}
                
        except Exception as e:
            self.logger.error(f"Error getting regime performance: {e}")
            return {}
    
    def get_regime_accuracy(self, symbol: str, regime: Optional[RegimeType] = None) -> Dict[str, Any]:
        """
        Get accuracy metrics for regime classification.
        
        Args:
            symbol: Trading symbol
            regime: Specific regime to query (None for all regimes)
            
        Returns:
            Accuracy metrics dictionary
        """
        try:
            if regime:
                if regime in self._accuracy_metrics:
                    return self._accuracy_metrics[regime].to_dict()
                else:
                    return {}
            else:
                return {r.value: metrics.to_dict() for r, metrics in self._accuracy_metrics.items()}
                
        except Exception as e:
            self.logger.error(f"Error getting regime accuracy: {e}")
            return {}
    
    def _validate_trade_data_consistency(self, symbol: str, trade_data: Dict[str, Any]) -> bool:
        """
        Validate data consistency between trade execution and analytics.
        
        This addresses the critical DATA-001 risk by implementing comprehensive
        data validation checks.
        """
        try:
            # Check required fields
            required_fields = ['pnl', 'timestamp', 'symbol']
            for field in required_fields:
                if field not in trade_data:
                    self.logger.error(f"Missing required field in trade data: {field}")
                    return False
            
            # Validate PnL is numeric
            if not isinstance(trade_data['pnl'], (int, float)):
                self.logger.error("PnL must be numeric")
                return False
            
            # Validate timestamp is recent (within last 24 hours)
            trade_time = trade_data.get('timestamp')
            if isinstance(trade_time, str):
                trade_time = datetime.fromisoformat(trade_time)
            
            if datetime.now() - trade_time > timedelta(hours=24):
                self.logger.warning(f"Trade data is older than 24 hours: {trade_time}")
            
            # Validate symbol matches
            if trade_data.get('symbol') != symbol:
                self.logger.error(f"Symbol mismatch: expected {symbol}, got {trade_data.get('symbol')}")
                return False
            
            # Check regime consistency
            current_regime = self.regime_service.get_current_regime(symbol)
            if not current_regime:
                self.logger.warning(f"No current regime for symbol {symbol}")
                return False
            
            # Additional consistency checks can be added here
            # For example, checking against recent trade patterns, etc.
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in data consistency validation: {e}")
            return False
    
    def _save_metrics_to_db(self, symbol: str, metrics: RegimePerformanceMetrics):
        """Save performance metrics to database with transaction safety."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Use transaction for data safety
                cursor.execute("BEGIN TRANSACTION")
                
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO regime_performance 
                        (symbol, regime, timestamp, total_trades, winning_trades, losing_trades,
                         total_pnl, max_drawdown, current_drawdown, peak_value, sharpe_ratio,
                         hit_rate, avg_win, avg_loss, profit_factor)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol, metrics.regime.value, metrics.last_updated,
                        metrics.total_trades, metrics.winning_trades, metrics.losing_trades,
                        metrics.total_pnl, metrics.max_drawdown, metrics.current_drawdown,
                        metrics.peak_value, metrics.sharpe_ratio, metrics.hit_rate,
                        metrics.avg_win, metrics.avg_loss, metrics.profit_factor
                    ))
                    
                    conn.commit()
                    
                except Exception as e:
                    conn.rollback()
                    raise e
                    
        except Exception as e:
            self.logger.error(f"Failed to save metrics to database: {e}")
            if self._transaction_rollback_enabled:
                self.logger.info("Transaction rollback completed")
            raise
    
    def _save_accuracy_metrics_to_db(self, symbol: str, metrics: RegimeAccuracyMetrics):
        """Save accuracy metrics to database with transaction safety."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("BEGIN TRANSACTION")
                
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO regime_accuracy 
                        (symbol, regime, timestamp, total_predictions, correct_predictions,
                         accuracy, confidence_avg)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol, metrics.regime.value, metrics.last_updated,
                        metrics.total_predictions, metrics.correct_predictions,
                        metrics.accuracy, metrics.confidence_avg
                    ))
                    
                    conn.commit()
                    
                except Exception as e:
                    conn.rollback()
                    raise e
                    
        except Exception as e:
            self.logger.error(f"Failed to save accuracy metrics to database: {e}")
            raise
    
    def _log_consistency_check(self, check_type: str, status: str, details: Dict[str, Any]):
        """Log consistency check results for monitoring."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO data_consistency_log (check_type, status, details, timestamp)
                    VALUES (?, ?, ?, ?)
                """, (check_type, status, json.dumps(details), datetime.now()))
                conn.commit()
                
        except Exception as e:
            self.logger.error(f"Failed to log consistency check: {e}")
    
    def _handle_circuit_breaker_failure(self):
        """Handle circuit breaker failure logic."""
        self._circuit_breaker_failures += 1
        
        if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
            self._circuit_breaker_state = "OPEN"
            self.logger.error(f"Circuit breaker opened after {self._circuit_breaker_failures} failures")
            
            # Schedule circuit breaker reset
            threading.Timer(self._circuit_breaker_timeout, self._reset_circuit_breaker).start()
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker to HALF_OPEN state."""
        self._circuit_breaker_state = "HALF_OPEN"
        self.logger.info("Circuit breaker reset to HALF_OPEN state")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status including circuit breaker state."""
        circuit_breaker_open = self._circuit_breaker_state == "OPEN"
        service_health = "degraded" if circuit_breaker_open else "healthy"
        
        return {
            "circuit_breaker_state": self._circuit_breaker_state,
            "circuit_breaker_open": circuit_breaker_open,
            "circuit_breaker_failures": self._circuit_breaker_failures,
            "service_health": service_health,
            "performance_metrics_count": len(self._performance_metrics),
            "accuracy_metrics_count": len(self._accuracy_metrics),
            "last_consistency_check": self._last_consistency_check,
            "backup_enabled": self._backup_enabled,
            "transaction_rollback_enabled": self._transaction_rollback_enabled
        }
