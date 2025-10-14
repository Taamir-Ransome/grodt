# Risk/Reward Ratio Configuration Design

## Overview

The risk/reward ratio configuration system allows traders to set predefined profit targets based on their risk tolerance. This ensures consistent risk management across all trades.

## Configuration Architecture

### Core Configuration Classes

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Union
from enum import Enum

class RiskRewardStrategy(Enum):
    """Risk/reward calculation strategies."""
    FIXED_RATIO = "fixed_ratio"
    ADAPTIVE_RATIO = "adaptive_ratio"
    VOLATILITY_BASED = "volatility_based"
    MARKET_CONDITION = "market_condition"

@dataclass
class RiskRewardConfig:
    """Risk/reward ratio configuration."""
    strategy: RiskRewardStrategy
    base_ratio: float
    min_ratio: float
    max_ratio: float
    volatility_factor: float = 1.0
    market_condition_factors: Dict[str, float] = None
    symbol_specific_ratios: Dict[str, float] = None
    
    def __post_init__(self):
        if self.market_condition_factors is None:
            self.market_condition_factors = {
                "trending": 1.2,
                "ranging": 1.0,
                "volatile": 0.8
            }
        if self.symbol_specific_ratios is None:
            self.symbol_specific_ratios = {}

class RiskRewardCalculator:
    """Calculates take profit levels based on risk/reward ratios."""
    
    def __init__(self, config: RiskRewardConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str,
        symbol: str = None,
        market_condition: str = "trending"
    ) -> float:
        """Calculate take profit price based on risk/reward ratio."""
        
        # Get effective ratio for this calculation
        effective_ratio = await self._get_effective_ratio(
            symbol, market_condition
        )
        
        # Calculate risk distance
        risk_distance = abs(entry_price - stop_loss_price)
        
        # Calculate reward distance
        reward_distance = risk_distance * effective_ratio
        
        # Calculate take profit price
        if side.lower() == 'buy':
            # For long positions, take profit is above entry
            take_profit = entry_price + reward_distance
        else:
            # For short positions, take profit is below entry
            take_profit = entry_price - reward_distance
        
        self.logger.info(
            f"Calculated take profit: {take_profit:.4f} "
            f"(entry: {entry_price:.4f}, risk: {risk_distance:.4f}, "
            f"ratio: {effective_ratio:.2f})"
        )
        
        return take_profit
    
    async def _get_effective_ratio(
        self,
        symbol: str = None,
        market_condition: str = "trending"
    ) -> float:
        """Get effective risk/reward ratio for calculation."""
        
        # Start with base ratio
        ratio = self.config.base_ratio
        
        # Apply symbol-specific ratio if available
        if symbol and symbol in self.config.symbol_specific_ratios:
            ratio = self.config.symbol_specific_ratios[symbol]
        
        # Apply market condition factor
        if market_condition in self.config.market_condition_factors:
            ratio *= self.config.market_condition_factors[market_condition]
        
        # Apply volatility factor
        ratio *= self.config.volatility_factor
        
        # Ensure ratio is within bounds
        ratio = max(self.config.min_ratio, min(ratio, self.config.max_ratio))
        
        return ratio
```

## Configuration Strategies

### 1. Fixed Ratio Strategy

```python
class FixedRatioStrategy:
    """Fixed risk/reward ratio strategy."""
    
    def __init__(self, ratio: float):
        self.ratio = ratio
    
    async def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str
    ) -> float:
        """Calculate take profit with fixed ratio."""
        
        risk_distance = abs(entry_price - stop_loss_price)
        reward_distance = risk_distance * self.ratio
        
        if side.lower() == 'buy':
            return entry_price + reward_distance
        else:
            return entry_price - reward_distance
```

### 2. Adaptive Ratio Strategy

```python
class AdaptiveRatioStrategy:
    """Adaptive risk/reward ratio based on market conditions."""
    
    def __init__(self, base_ratio: float, volatility_factor: float = 1.0):
        self.base_ratio = base_ratio
        self.volatility_factor = volatility_factor
    
    async def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str,
        atr_value: float,
        market_volatility: float
    ) -> float:
        """Calculate take profit with adaptive ratio."""
        
        # Adjust ratio based on volatility
        adjusted_ratio = self.base_ratio * (1 + market_volatility * self.volatility_factor)
        
        risk_distance = abs(entry_price - stop_loss_price)
        reward_distance = risk_distance * adjusted_ratio
        
        if side.lower() == 'buy':
            return entry_price + reward_distance
        else:
            return entry_price - reward_distance
```

### 3. Volatility-Based Strategy

```python
class VolatilityBasedStrategy:
    """Risk/reward ratio based on market volatility."""
    
    def __init__(self, base_ratio: float, volatility_threshold: float = 0.02):
        self.base_ratio = base_ratio
        self.volatility_threshold = volatility_threshold
    
    async def calculate_take_profit(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str,
        atr_value: float,
        current_volatility: float
    ) -> float:
        """Calculate take profit based on volatility."""
        
        # Adjust ratio based on volatility
        if current_volatility > self.volatility_threshold:
            # High volatility - use lower ratio for quicker exits
            ratio = self.base_ratio * 0.8
        else:
            # Low volatility - use higher ratio for better rewards
            ratio = self.base_ratio * 1.2
        
        risk_distance = abs(entry_price - stop_loss_price)
        reward_distance = risk_distance * ratio
        
        if side.lower() == 'buy':
            return entry_price + reward_distance
        else:
            return entry_price - reward_distance
```

## Configuration Management

### Configuration Loader

```python
class RiskRewardConfigLoader:
    """Loads and validates risk/reward configuration."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)
    
    async def load_config(self) -> RiskRewardConfig:
        """Load configuration from file."""
        
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            return RiskRewardConfig(
                strategy=RiskRewardStrategy(config_data['strategy']),
                base_ratio=config_data['base_ratio'],
                min_ratio=config_data['min_ratio'],
                max_ratio=config_data['max_ratio'],
                volatility_factor=config_data.get('volatility_factor', 1.0),
                market_condition_factors=config_data.get('market_condition_factors', {}),
                symbol_specific_ratios=config_data.get('symbol_specific_ratios', {})
            )
            
        except Exception as e:
            self.logger.error(f"Failed to load risk/reward config: {e}")
            raise
    
    async def validate_config(self, config: RiskRewardConfig) -> bool:
        """Validate configuration values."""
        
        if config.base_ratio <= 0:
            raise ValueError("Base ratio must be positive")
        
        if config.min_ratio <= 0 or config.max_ratio <= 0:
            raise ValueError("Min and max ratios must be positive")
        
        if config.min_ratio > config.max_ratio:
            raise ValueError("Min ratio cannot be greater than max ratio")
        
        if config.base_ratio < config.min_ratio or config.base_ratio > config.max_ratio:
            raise ValueError("Base ratio must be within min/max bounds")
        
        return True
```

### Dynamic Configuration Updates

```python
class DynamicConfigManager:
    """Manages dynamic configuration updates."""
    
    def __init__(self, config: RiskRewardConfig):
        self.config = config
        self.update_callbacks: List[Callable] = []
        self.logger = logging.getLogger(__name__)
    
    async def update_volatility_factor(
        self,
        new_factor: float
    ) -> None:
        """Update volatility factor dynamically."""
        
        old_factor = self.config.volatility_factor
        self.config.volatility_factor = new_factor
        
        self.logger.info(f"Updated volatility factor: {old_factor} -> {new_factor}")
        
        # Trigger update callbacks
        await self._trigger_update_callbacks("volatility_factor_updated", {
            "old_factor": old_factor,
            "new_factor": new_factor
        })
    
    async def update_symbol_specific_ratio(
        self,
        symbol: str,
        ratio: float
    ) -> None:
        """Update symbol-specific ratio."""
        
        self.config.symbol_specific_ratios[symbol] = ratio
        
        self.logger.info(f"Updated ratio for {symbol}: {ratio}")
        
        # Trigger update callbacks
        await self._trigger_update_callbacks("symbol_ratio_updated", {
            "symbol": symbol,
            "ratio": ratio
        })
    
    async def _trigger_update_callbacks(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """Trigger configuration update callbacks."""
        
        for callback in self.update_callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Error in config update callback: {e}")
```

## Configuration Files

### YAML Configuration

```yaml
# configs/risk_reward.yaml
risk_reward:
  strategy: "fixed_ratio"  # fixed_ratio, adaptive_ratio, volatility_based
  base_ratio: 1.5
  min_ratio: 1.0
  max_ratio: 3.0
  volatility_factor: 1.0
  
  market_condition_factors:
    trending: 1.2
    ranging: 1.0
    volatile: 0.8
  
  symbol_specific_ratios:
    AAPL: 1.8
    TSLA: 2.0
    SPY: 1.2
  
  # Advanced settings
  adaptive_settings:
    volatility_threshold: 0.02
    market_condition_lookback: 20
    ratio_adjustment_factor: 0.1
```

### Environment-Based Configuration

```python
class EnvironmentConfigLoader:
    """Loads configuration from environment variables."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    async def load_from_env(self) -> RiskRewardConfig:
        """Load configuration from environment variables."""
        
        return RiskRewardConfig(
            strategy=RiskRewardStrategy(os.getenv('RISK_REWARD_STRATEGY', 'fixed_ratio')),
            base_ratio=float(os.getenv('RISK_REWARD_BASE_RATIO', '1.5')),
            min_ratio=float(os.getenv('RISK_REWARD_MIN_RATIO', '1.0')),
            max_ratio=float(os.getenv('RISK_REWARD_MAX_RATIO', '3.0')),
            volatility_factor=float(os.getenv('RISK_REWARD_VOLATILITY_FACTOR', '1.0'))
        )
```

## Validation and Error Handling

### Configuration Validation

```python
class ConfigValidator:
    """Validates risk/reward configuration."""
    
    @staticmethod
    def validate_ratio(ratio: float, min_ratio: float, max_ratio: float) -> bool:
        """Validate ratio is within bounds."""
        return min_ratio <= ratio <= max_ratio
    
    @staticmethod
    def validate_strategy(strategy: str) -> bool:
        """Validate strategy is supported."""
        return strategy in [s.value for s in RiskRewardStrategy]
    
    @staticmethod
    def validate_market_conditions(factors: Dict[str, float]) -> bool:
        """Validate market condition factors."""
        return all(0 < factor < 5.0 for factor in factors.values())
```

## Testing Strategy

### Unit Tests
- Configuration loading and validation
- Ratio calculations for different strategies
- Dynamic configuration updates
- Error handling scenarios

### Integration Tests
- End-to-end configuration flow
- Strategy switching
- Symbol-specific configurations
- Market condition adaptations

### Performance Tests
- Configuration loading speed
- Dynamic updates performance
- Memory usage with large configurations
- Concurrent configuration access
