"""
Strategy Gating Service.

This module provides regime-based strategy gating functionality that enables
or disables strategies based on the current market regime.
"""

import logging
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from grodtd.regime.service import RegimeStateService, get_regime_service
from grodtd.regime.classifier import RegimeType


class StrategyType(Enum):
    """Strategy types for gating."""
    S1_TREND = "S1TrendStrategy"
    S2_RANGING = "S2RangingStrategy"  # Future
    S3_TREND = "S3TrendStrategy"     # Future


@dataclass
class GatingDecision:
    """Represents a strategy gating decision."""
    strategy_name: str
    enabled: bool
    regime: Optional[RegimeType]
    confidence: float
    reasoning: str
    override_applied: bool = False
    timestamp: Optional[str] = None


@dataclass
class GatingConfig:
    """Configuration for strategy gating."""
    # Regime-strategy mappings
    regime_strategy_mappings: Dict[str, List[str]]
    
    # Override settings
    manual_overrides: Dict[str, bool] = None
    override_enabled: bool = True
    
    # Fallback behavior
    fallback_enabled: bool = True
    fallback_strategies: List[str] = None
    
    # Performance settings
    max_decision_latency_ms: float = 10.0
    confidence_threshold: float = 0.5


class StrategyGatingService:
    """
    Service for managing strategy gating based on market regime.
    
    This service determines which strategies should be enabled or disabled
    based on the current market regime, with support for manual overrides
    and fallback behavior.
    """
    
    def __init__(self, config_path: Optional[str] = None, regime_service: Optional[RegimeStateService] = None):
        self.logger = logging.getLogger(__name__)
        self.regime_service = regime_service or get_regime_service()
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Decision history for logging
        self._decision_history: List[GatingDecision] = []
        self._max_history_size = 1000
        
        self.logger.info("StrategyGatingService initialized")
    
    def _load_config(self, config_path: Optional[str] = None) -> GatingConfig:
        """Load gating configuration from YAML file."""
        if config_path is None:
            config_path = "configs/strategy_gating.yaml"
        
        config_file = Path(config_path)
        if not config_file.exists():
            # Create default configuration
            self._create_default_config(config_file)
        
        try:
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            
            # Validate configuration
            self._validate_config(config_data)
            
            return GatingConfig(
                regime_strategy_mappings=config_data.get('regime_strategy_mappings', {}),
                manual_overrides=config_data.get('manual_overrides', {}),
                override_enabled=config_data.get('override_enabled', True),
                fallback_enabled=config_data.get('fallback_enabled', True),
                fallback_strategies=config_data.get('fallback_strategies', []),
                max_decision_latency_ms=config_data.get('max_decision_latency_ms', 10.0),
                confidence_threshold=config_data.get('confidence_threshold', 0.5)
            )
        except Exception as e:
            self.logger.error(f"Error loading gating config: {e}")
            # Return default configuration
            return self._get_default_config()
    
    def _validate_config(self, config_data: Dict[str, Any]):
        """Validate configuration data."""
        # Validate regime_strategy_mappings if present
        if 'regime_strategy_mappings' in config_data:
            regime_mappings = config_data['regime_strategy_mappings']
            if not isinstance(regime_mappings, dict):
                raise ValueError("'regime_strategy_mappings' must be a dictionary")
        
            # Validate regime types
            valid_regimes = ['trending', 'ranging', 'transition', 'high_volatility']
            for regime in regime_mappings.keys():
                if regime not in valid_regimes:
                    self.logger.warning(f"Unknown regime type: {regime}")
            
            # Validate strategy lists
            for regime, strategies in regime_mappings.items():
                if not isinstance(strategies, list):
                    raise ValueError(f"Strategies for regime '{regime}' must be a list")
                for strategy in strategies:
                    if not isinstance(strategy, str):
                        raise ValueError(f"Strategy names must be strings, got: {type(strategy)}")
        
        # Validate numeric values
        if 'max_decision_latency_ms' in config_data:
            latency = config_data['max_decision_latency_ms']
            if not isinstance(latency, (int, float)) or latency <= 0:
                raise ValueError("'max_decision_latency_ms' must be a positive number")
        
        if 'confidence_threshold' in config_data:
            threshold = config_data['confidence_threshold']
            if not isinstance(threshold, (int, float)) or not (0.0 <= threshold <= 1.0):
                raise ValueError("'confidence_threshold' must be between 0.0 and 1.0")
        
        # Validate boolean values
        for bool_key in ['override_enabled', 'fallback_enabled']:
            if bool_key in config_data:
                if not isinstance(config_data[bool_key], bool):
                    raise ValueError(f"'{bool_key}' must be a boolean")
        
        self.logger.info("Configuration validation passed")
    
    def _create_default_config(self, config_file: Path):
        """Create default configuration file."""
        default_config = {
            'regime_strategy_mappings': {
                'trending': ['S1TrendStrategy', 'S3TrendStrategy'],
                'ranging': ['S2RangingStrategy'],
                'transition': [],
                'high_volatility': []
            },
            'manual_overrides': {},
            'override_enabled': True,
            'fallback_enabled': True,
            'fallback_strategies': [],
            'max_decision_latency_ms': 10.0,
            'confidence_threshold': 0.5
        }
        
        try:
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            self.logger.info(f"Created default gating config at {config_file}")
        except Exception as e:
            self.logger.error(f"Error creating default config: {e}")
    
    def _get_default_config(self) -> GatingConfig:
        """Get default configuration."""
        return GatingConfig(
            regime_strategy_mappings={
                'trending': ['S1TrendStrategy', 'S3TrendStrategy'],
                'ranging': ['S2RangingStrategy'],
                'transition': [],
                'high_volatility': []
            },
            manual_overrides={},
            override_enabled=True,
            fallback_enabled=True,
            fallback_strategies=[],
            max_decision_latency_ms=10.0,
            confidence_threshold=0.5
        )
    
    def is_strategy_enabled(self, strategy_name: str, symbol: str) -> GatingDecision:
        """
        Determine if a strategy should be enabled for a symbol.
        
        Args:
            strategy_name: Name of the strategy to check
            symbol: Symbol to check for
            
        Returns:
            GatingDecision with the decision and reasoning
        """
        import time
        start_time = time.time()
        
        try:
            # Check for manual override first
            if self.config.override_enabled and self.config.manual_overrides and strategy_name in self.config.manual_overrides:
                override_value = self.config.manual_overrides[strategy_name]
                decision = GatingDecision(
                    strategy_name=strategy_name,
                    enabled=override_value,
                    regime=None,
                    confidence=1.0,
                    reasoning=f"Manual override: {override_value}",
                    override_applied=True,
                    timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
                )
                self._log_decision(decision)
                return decision
            
            # Get current regime
            regime = self.regime_service.get_current_regime(symbol)
            confidence = self.regime_service.get_regime_confidence(symbol)
            
            # Check if regime is stale
            is_stale = self.regime_service.is_regime_stale(symbol)
            
            # Determine if strategy should be enabled based on regime
            enabled = self._should_enable_strategy(strategy_name, regime, confidence, is_stale)
            
            # Generate reasoning
            reasoning = self._generate_reasoning(strategy_name, regime, confidence, is_stale, enabled)
            
            decision = GatingDecision(
                strategy_name=strategy_name,
                enabled=enabled,
                regime=regime,
                confidence=confidence,
                reasoning=reasoning,
                override_applied=False,
                timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
            )
            
            # Check performance requirement
            decision_time = (time.time() - start_time) * 1000
            if decision_time > self.config.max_decision_latency_ms:
                self.logger.warning(f"Gating decision took {decision_time:.2f}ms, exceeds {self.config.max_decision_latency_ms}ms limit")
            
            self._log_decision(decision)
            return decision
            
        except Exception as e:
            self.logger.error(f"Error in gating decision for {strategy_name}: {e}")
            # Return fallback decision
            return self._get_fallback_decision(strategy_name)
    
    def _should_enable_strategy(self, strategy_name: str, regime: Optional[RegimeType], 
                              confidence: float, is_stale: bool) -> bool:
        """Determine if strategy should be enabled based on regime."""
        
        # If regime is stale or confidence is low, use fallback behavior
        if is_stale or confidence < self.config.confidence_threshold:
            if self.config.fallback_enabled and self.config.fallback_strategies:
                return strategy_name in self.config.fallback_strategies
            else:
                # Conservative fallback: disable all strategies
                return False
        
        # If no regime available, use fallback
        if regime is None:
            if self.config.fallback_enabled and self.config.fallback_strategies:
                return strategy_name in self.config.fallback_strategies
            else:
                return False
        
        # Check regime-strategy mapping
        regime_key = regime.value
        enabled_strategies = self.config.regime_strategy_mappings.get(regime_key, [])
        
        return strategy_name in enabled_strategies
    
    def _generate_reasoning(self, strategy_name: str, regime: Optional[RegimeType], 
                          confidence: float, is_stale: bool, enabled: bool) -> str:
        """Generate human-readable reasoning for the decision."""
        reasons = []
        
        if regime is None:
            reasons.append("No regime data available")
        else:
            reasons.append(f"Current regime: {regime.value}")
            reasons.append(f"Confidence: {confidence:.2f}")
        
        if is_stale:
            reasons.append("Regime data is stale")
        
        if confidence < self.config.confidence_threshold:
            reasons.append(f"Low confidence ({confidence:.2f} < {self.config.confidence_threshold})")
        
        if regime is not None:
            regime_key = regime.value
            enabled_strategies = self.config.regime_strategy_mappings.get(regime_key, [])
            if enabled:
                reasons.append(f"Strategy enabled for {regime_key} regime")
            else:
                reasons.append(f"Strategy not enabled for {regime_key} regime (enabled: {enabled_strategies})")
        
        if not reasons:
            reasons.append("No specific reasoning available")
        
        return "; ".join(reasons)
    
    def _get_fallback_decision(self, strategy_name: str) -> GatingDecision:
        """Get fallback decision when errors occur."""
        import time
        
        enabled = False
        if self.config.fallback_enabled and self.config.fallback_strategies:
            enabled = strategy_name in self.config.fallback_strategies
        
        return GatingDecision(
            strategy_name=strategy_name,
            enabled=enabled,
            regime=None,
            confidence=0.0,
            reasoning=f"Fallback decision due to error (enabled: {enabled})",
            override_applied=False,
            timestamp=time.strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def _log_decision(self, decision: GatingDecision):
        """Log and store the gating decision."""
        # Add to history
        self._decision_history.append(decision)
        
        # Maintain history size
        if len(self._decision_history) > self._max_history_size:
            self._decision_history = self._decision_history[-self._max_history_size:]
        
        # Log decision
        self.logger.info(
            f"Gating decision for {decision.strategy_name}: "
            f"enabled={decision.enabled}, regime={decision.regime}, "
            f"confidence={decision.confidence:.2f}, reasoning={decision.reasoning}"
        )
    
    def get_enabled_strategies(self, symbol: str, available_strategies: List[str]) -> List[str]:
        """
        Get list of enabled strategies for a symbol.
        
        Args:
            symbol: Symbol to check
            available_strategies: List of available strategy names
            
        Returns:
            List of enabled strategy names
        """
        enabled_strategies = []
        
        for strategy_name in available_strategies:
            decision = self.is_strategy_enabled(strategy_name, symbol)
            if decision.enabled:
                enabled_strategies.append(strategy_name)
        
        self.logger.info(f"Enabled strategies for {symbol}: {enabled_strategies}")
        return enabled_strategies
    
    def set_manual_override(self, strategy_name: str, enabled: bool):
        """Set manual override for a strategy."""
        if self.config.manual_overrides is None:
            self.config.manual_overrides = {}
        self.config.manual_overrides[strategy_name] = enabled
        self.logger.info(f"Set manual override for {strategy_name}: {enabled}")
    
    def clear_manual_override(self, strategy_name: str):
        """Clear manual override for a strategy."""
        if self.config.manual_overrides and strategy_name in self.config.manual_overrides:
            del self.config.manual_overrides[strategy_name]
            self.logger.info(f"Cleared manual override for {strategy_name}")
    
    def get_decision_history(self, strategy_name: Optional[str] = None, 
                           limit: int = 100) -> List[GatingDecision]:
        """Get decision history."""
        history = self._decision_history
        
        if strategy_name:
            history = [d for d in history if d.strategy_name == strategy_name]
        
        return history[-limit:] if limit > 0 else history
    
    def get_gating_summary(self, symbol: str) -> Dict[str, Any]:
        """Get comprehensive gating summary for a symbol."""
        regime = self.regime_service.get_current_regime(symbol)
        confidence = self.regime_service.get_regime_confidence(symbol)
        is_stale = self.regime_service.is_regime_stale(symbol)
        
        return {
            'symbol': symbol,
            'current_regime': regime.value if regime else None,
            'regime_confidence': confidence,
            'regime_stale': is_stale,
            'manual_overrides': self.config.manual_overrides.copy() if self.config.manual_overrides else {},
            'override_enabled': self.config.override_enabled,
            'fallback_enabled': self.config.fallback_enabled,
            'fallback_strategies': self.config.fallback_strategies.copy(),
            'recent_decisions': self.get_decision_history(limit=10)
        }
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update configuration with validation."""
        try:
            # Validate new configuration
            self._validate_config(new_config)
            
            # Update configuration
            if 'regime_strategy_mappings' in new_config:
                self.config.regime_strategy_mappings = new_config['regime_strategy_mappings']
            
            if 'manual_overrides' in new_config:
                self.config.manual_overrides = new_config['manual_overrides']
            
            if 'override_enabled' in new_config:
                self.config.override_enabled = new_config['override_enabled']
            
            if 'fallback_enabled' in new_config:
                self.config.fallback_enabled = new_config['fallback_enabled']
            
            if 'fallback_strategies' in new_config:
                self.config.fallback_strategies = new_config['fallback_strategies']
            
            if 'max_decision_latency_ms' in new_config:
                self.config.max_decision_latency_ms = new_config['max_decision_latency_ms']
            
            if 'confidence_threshold' in new_config:
                self.config.confidence_threshold = new_config['confidence_threshold']
            
            self.logger.info("Configuration updated successfully")
            
        except Exception as e:
            self.logger.error(f"Error updating configuration: {e}")
            raise
    
    def save_config(self, config_path: Optional[str] = None):
        """Save current configuration to file."""
        if config_path is None:
            config_path = "configs/strategy_gating.yaml"
        
        config_file = Path(config_path)
        
        try:
            config_data = {
                'regime_strategy_mappings': self.config.regime_strategy_mappings,
                'manual_overrides': self.config.manual_overrides if self.config.manual_overrides is not None else {},
                'override_enabled': self.config.override_enabled,
                'fallback_enabled': self.config.fallback_enabled,
                'fallback_strategies': self.config.fallback_strategies if self.config.fallback_strategies is not None else [],
                'max_decision_latency_ms': self.config.max_decision_latency_ms,
                'confidence_threshold': self.config.confidence_threshold
            }
            
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
            
            self.logger.info(f"Configuration saved to {config_file}")
            
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            raise


# Factory function for creating gating service
def create_strategy_gating_service(config_path: Optional[str] = None, 
                                 regime_service: Optional[RegimeStateService] = None) -> StrategyGatingService:
    """Create a new strategy gating service."""
    return StrategyGatingService(config_path, regime_service)
