"""
Comprehensive logging for regime classification decisions.

This module provides detailed logging capabilities for regime classification,
including decision tracking, feature logging, and performance monitoring.
"""

import logging
import json
import csv
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import numpy as np
from dataclasses import dataclass, asdict
from enum import Enum

# Import RegimeType and RegimeFeatures at runtime to avoid circular imports


class LogLevel(Enum):
    """Logging levels for regime classification."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class ClassificationDecision:
    """Record of a regime classification decision."""
    timestamp: datetime
    symbol: str
    regime: str
    confidence: float
    features: Dict[str, float]
    reasoning: str
    performance_ms: float
    data_quality: str


@dataclass
class RegimeTransition:
    """Record of a regime transition."""
    timestamp: datetime
    symbol: str
    from_regime: str
    to_regime: str
    from_confidence: float
    to_confidence: float
    transition_duration_minutes: float
    trigger_features: Dict[str, float]


class RegimeLogger:
    """
    Comprehensive logger for regime classification decisions and transitions.
    
    This logger provides detailed tracking of all regime classification
    decisions, feature calculations, and regime transitions for analysis
    and debugging purposes.
    """
    
    def __init__(self, log_dir: Optional[str] = None, enable_file_logging: bool = True):
        self.log_dir = Path(log_dir) if log_dir else Path("logs/regime")
        self.enable_file_logging = enable_file_logging
        self.logger = logging.getLogger(__name__)
        
        # In-memory storage for recent decisions
        self._decisions: List[ClassificationDecision] = []
        self._transitions: List[RegimeTransition] = []
        self._performance_metrics: Dict[str, List[float]] = {}
        
        # Setup file logging if enabled
        if self.enable_file_logging:
            self._setup_file_logging()
        
        # Configuration
        self.max_memory_decisions = 1000  # Keep last 1000 decisions in memory
        self.log_feature_values = True
        self.log_performance = True
        
        self.logger.info("RegimeLogger initialized")
    
    def _setup_file_logging(self):
        """Setup file-based logging."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            # Setup CSV logging for decisions
            self.decisions_file = self.log_dir / "regime_decisions.csv"
            self.transitions_file = self.log_dir / "regime_transitions.csv"
            self.performance_file = self.log_dir / "regime_performance.csv"
            
            # Initialize CSV files with headers
            self._initialize_csv_files()
            
        except Exception as e:
            self.logger.error(f"Failed to setup file logging: {e}")
            self.enable_file_logging = False
    
    def _initialize_csv_files(self):
        """Initialize CSV files with appropriate headers."""
        # Decisions file
        if not self.decisions_file.exists():
            with open(self.decisions_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'regime', 'confidence', 'vwap_slope',
                    'atr_percentile', 'volatility_ratio', 'price_momentum',
                    'volume_trend', 'reasoning', 'performance_ms', 'data_quality'
                ])
        
        # Transitions file
        if not self.transitions_file.exists():
            with open(self.transitions_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'from_regime', 'to_regime',
                    'from_confidence', 'to_confidence', 'transition_duration_minutes',
                    'trigger_vwap_slope', 'trigger_atr_percentile', 'trigger_volatility_ratio'
                ])
        
        # Performance file
        if not self.performance_file.exists():
            with open(self.performance_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'classification_time_ms', 'feature_calc_time_ms',
                    'total_time_ms', 'memory_usage_mb'
                ])
    
    def log_classification_decision(
        self,
        symbol: str,
        regime,  # RegimeType - imported at runtime
        confidence: float,
        features,  # RegimeFeatures - imported at runtime
        reasoning: str,
        performance_ms: float,
        data_quality: str = "good"
    ):
        """
        Log a regime classification decision.
        
        Args:
            symbol: Symbol being classified
            regime: Classified regime
            confidence: Classification confidence
            features: Calculated features
            reasoning: Human-readable reasoning
            performance_ms: Time taken for classification
            data_quality: Quality of input data
        """
        decision = ClassificationDecision(
            timestamp=datetime.now(),
            symbol=symbol,
            regime=regime.value,
            confidence=confidence,
            features={
                'vwap_slope': features.vwap_slope,
                'atr_percentile': features.atr_percentile,
                'volatility_ratio': features.volatility_ratio,
                'price_momentum': features.price_momentum,
                'volume_trend': features.volume_trend
            },
            reasoning=reasoning,
            performance_ms=performance_ms,
            data_quality=data_quality
        )
        
        # Store in memory
        self._decisions.append(decision)
        if len(self._decisions) > self.max_memory_decisions:
            self._decisions = self._decisions[-self.max_memory_decisions:]
        
        # Log to file
        if self.enable_file_logging:
            self._write_decision_to_file(decision)
        
        # Log to standard logger
        self.logger.info(
            f"Regime classification for {symbol}: {regime.value} "
            f"(confidence: {confidence:.2f}, reasoning: {reasoning})"
        )
        
        # Log feature values if enabled
        if self.log_feature_values:
            self.logger.debug(
                f"Features for {symbol}: VWAP slope={features.vwap_slope:.6f}, "
                f"ATR percentile={features.atr_percentile:.3f}, "
                f"volatility ratio={features.volatility_ratio:.3f}, "
                f"momentum={features.price_momentum:.4f}, "
                f"volume trend={features.volume_trend:.3f}"
            )
    
    def log_regime_transition(
        self,
        symbol: str,
        from_regime,  # RegimeType - imported at runtime
        to_regime,    # RegimeType - imported at runtime
        from_confidence: float,
        to_confidence: float,
        transition_duration_minutes: float,
        trigger_features  # RegimeFeatures - imported at runtime
    ):
        """
        Log a regime transition.
        
        Args:
            symbol: Symbol with transition
            from_regime: Previous regime
            to_regime: New regime
            from_confidence: Previous confidence
            to_confidence: New confidence
            transition_duration_minutes: Duration of previous regime
            trigger_features: Features that triggered the transition
        """
        transition = RegimeTransition(
            timestamp=datetime.now(),
            symbol=symbol,
            from_regime=from_regime.value,
            to_regime=to_regime.value,
            from_confidence=from_confidence,
            to_confidence=to_confidence,
            transition_duration_minutes=transition_duration_minutes,
            trigger_features={
                'vwap_slope': trigger_features.vwap_slope,
                'atr_percentile': trigger_features.atr_percentile,
                'volatility_ratio': trigger_features.volatility_ratio,
                'price_momentum': trigger_features.price_momentum,
                'volume_trend': trigger_features.volume_trend
            }
        )
        
        # Store in memory
        self._transitions.append(transition)
        if len(self._transitions) > 500:  # Keep last 500 transitions
            self._transitions = self._transitions[-500:]
        
        # Log to file
        if self.enable_file_logging:
            self._write_transition_to_file(transition)
        
        # Log to standard logger
        self.logger.info(
            f"Regime transition for {symbol}: {from_regime.value} -> {to_regime.value} "
            f"(duration: {transition_duration_minutes:.1f}min, "
            f"confidence: {from_confidence:.2f} -> {to_confidence:.2f})"
        )
    
    def log_performance_metrics(
        self,
        symbol: str,
        classification_time_ms: float,
        feature_calc_time_ms: float,
        total_time_ms: float,
        memory_usage_mb: float
    ):
        """
        Log performance metrics for regime classification.
        
        Args:
            symbol: Symbol being processed
            classification_time_ms: Time for classification logic
            feature_calc_time_ms: Time for feature calculation
            total_time_ms: Total processing time
            memory_usage_mb: Memory usage in MB
        """
        if not self.log_performance:
            return
        
        # Store in memory
        if symbol not in self._performance_metrics:
            self._performance_metrics[symbol] = []
        
        self._performance_metrics[symbol].append({
            'timestamp': datetime.now(),
            'classification_time_ms': classification_time_ms,
            'feature_calc_time_ms': feature_calc_time_ms,
            'total_time_ms': total_time_ms,
            'memory_usage_mb': memory_usage_mb
        })
        
        # Keep only last 100 performance records per symbol
        if len(self._performance_metrics[symbol]) > 100:
            self._performance_metrics[symbol] = self._performance_metrics[symbol][-100:]
        
        # Log to file
        if self.enable_file_logging:
            self._write_performance_to_file(symbol, {
                'timestamp': datetime.now(),
                'classification_time_ms': classification_time_ms,
                'feature_calc_time_ms': feature_calc_time_ms,
                'total_time_ms': total_time_ms,
                'memory_usage_mb': memory_usage_mb
            })
        
        # Log performance warnings
        if total_time_ms > 1000:  # More than 1 second
            self.logger.warning(
                f"Slow regime classification for {symbol}: {total_time_ms:.1f}ms"
            )
    
    def _write_decision_to_file(self, decision: ClassificationDecision):
        """Write decision to CSV file."""
        try:
            with open(self.decisions_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    decision.timestamp.isoformat(),
                    decision.symbol,
                    decision.regime,
                    decision.confidence,
                    decision.features['vwap_slope'],
                    decision.features['atr_percentile'],
                    decision.features['volatility_ratio'],
                    decision.features['price_momentum'],
                    decision.features['volume_trend'],
                    decision.reasoning,
                    decision.performance_ms,
                    decision.data_quality
                ])
        except Exception as e:
            self.logger.error(f"Failed to write decision to file: {e}")
    
    def _write_transition_to_file(self, transition: RegimeTransition):
        """Write transition to CSV file."""
        try:
            with open(self.transitions_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    transition.timestamp.isoformat(),
                    transition.symbol,
                    transition.from_regime,
                    transition.to_regime,
                    transition.from_confidence,
                    transition.to_confidence,
                    transition.transition_duration_minutes,
                    transition.trigger_features['vwap_slope'],
                    transition.trigger_features['atr_percentile'],
                    transition.trigger_features['volatility_ratio']
                ])
        except Exception as e:
            self.logger.error(f"Failed to write transition to file: {e}")
    
    def _write_performance_to_file(self, symbol: str, metrics: Dict[str, Any]):
        """Write performance metrics to CSV file."""
        try:
            with open(self.performance_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    metrics['timestamp'].isoformat(),
                    symbol,
                    metrics['classification_time_ms'],
                    metrics['feature_calc_time_ms'],
                    metrics['total_time_ms'],
                    metrics['memory_usage_mb']
                ])
        except Exception as e:
            self.logger.error(f"Failed to write performance to file: {e}")
    
    def get_recent_decisions(self, symbol: Optional[str] = None, hours: int = 24) -> List[ClassificationDecision]:
        """
        Get recent classification decisions.
        
        Args:
            symbol: Optional symbol filter
            hours: Number of hours to look back
            
        Returns:
            List of recent decisions
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if symbol:
            return [d for d in self._decisions 
                   if d.symbol == symbol and d.timestamp >= cutoff_time]
        else:
            return [d for d in self._decisions if d.timestamp >= cutoff_time]
    
    def get_recent_transitions(self, symbol: Optional[str] = None, hours: int = 24) -> List[RegimeTransition]:
        """
        Get recent regime transitions.
        
        Args:
            symbol: Optional symbol filter
            hours: Number of hours to look back
            
        Returns:
            List of recent transitions
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if symbol:
            return [t for t in self._transitions 
                   if t.symbol == symbol and t.timestamp >= cutoff_time]
        else:
            return [t for t in self._transitions if t.timestamp >= cutoff_time]
    
    def get_performance_summary(self, symbol: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
        """
        Get performance summary for regime classification.
        
        Args:
            symbol: Optional symbol filter
            hours: Number of hours to analyze
            
        Returns:
            Performance summary dictionary
        """
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if symbol:
            metrics = self._performance_metrics.get(symbol, [])
        else:
            metrics = []
            for symbol_metrics in self._performance_metrics.values():
                metrics.extend(symbol_metrics)
        
        # Filter by time
        recent_metrics = [m for m in metrics if m['timestamp'] >= cutoff_time]
        
        if not recent_metrics:
            return {'error': 'No performance data available'}
        
        # Calculate summary statistics
        total_times = [m['total_time_ms'] for m in recent_metrics]
        classification_times = [m['classification_time_ms'] for m in recent_metrics]
        memory_usage = [m['memory_usage_mb'] for m in recent_metrics]
        
        return {
            'total_classifications': len(recent_metrics),
            'avg_total_time_ms': np.mean(total_times),
            'max_total_time_ms': np.max(total_times),
            'avg_classification_time_ms': np.mean(classification_times),
            'max_classification_time_ms': np.max(classification_times),
            'avg_memory_usage_mb': np.mean(memory_usage),
            'max_memory_usage_mb': np.max(memory_usage),
            'time_period_hours': hours
        }
    
    def get_regime_accuracy_analysis(self, symbol: Optional[str] = None, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze regime classification accuracy.
        
        Args:
            symbol: Optional symbol filter
            hours: Number of hours to analyze
            
        Returns:
            Accuracy analysis dictionary
        """
        decisions = self.get_recent_decisions(symbol, hours)
        transitions = self.get_recent_transitions(symbol, hours)
        
        if not decisions:
            return {'error': 'No classification data available'}
        
        # Calculate accuracy metrics
        total_decisions = len(decisions)
        high_confidence_decisions = len([d for d in decisions if d.confidence >= 0.8])
        low_confidence_decisions = len([d for d in decisions if d.confidence < 0.6])
        
        # Calculate regime distribution
        regime_counts = {}
        for decision in decisions:
            regime = decision.regime
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        # Calculate transition frequency
        transition_frequency = len(transitions) / (hours / 24) if hours > 0 else 0  # Transitions per day
        
        return {
            'total_decisions': total_decisions,
            'high_confidence_ratio': high_confidence_decisions / total_decisions if total_decisions > 0 else 0,
            'low_confidence_ratio': low_confidence_decisions / total_decisions if total_decisions > 0 else 0,
            'regime_distribution': regime_counts,
            'transition_frequency_per_day': transition_frequency,
            'avg_confidence': np.mean([d.confidence for d in decisions]),
            'time_period_hours': hours
        }
    
    def export_analysis_report(self, output_file: str, symbol: Optional[str] = None, hours: int = 24):
        """
        Export a comprehensive analysis report.
        
        Args:
            output_file: Path to output file
            symbol: Optional symbol filter
            hours: Number of hours to analyze
        """
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol or 'all',
                'time_period_hours': hours,
                'performance_summary': self.get_performance_summary(symbol, hours),
                'accuracy_analysis': self.get_regime_accuracy_analysis(symbol, hours),
                'recent_decisions': [asdict(d) for d in self.get_recent_decisions(symbol, hours)],
                'recent_transitions': [asdict(t) for t in self.get_recent_transitions(symbol, hours)]
            }
            
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            self.logger.info(f"Analysis report exported to {output_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to export analysis report: {e}")


# Global logger instance
_regime_logger: Optional[RegimeLogger] = None


def get_regime_logger() -> RegimeLogger:
    """Get the global regime logger."""
    global _regime_logger
    if _regime_logger is None:
        _regime_logger = RegimeLogger()
    return _regime_logger


def initialize_regime_logger(log_dir: Optional[str] = None, enable_file_logging: bool = True) -> RegimeLogger:
    """Initialize the global regime logger."""
    global _regime_logger
    _regime_logger = RegimeLogger(log_dir, enable_file_logging)
    return _regime_logger
