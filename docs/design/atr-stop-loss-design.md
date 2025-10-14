# ATR-Based Stop Loss Calculations Design

## Overview

The Average True Range (ATR) is used to calculate dynamic stop loss levels based on market volatility. This provides more adaptive risk management compared to fixed percentage stops.

## ATR Calculation

### Core ATR Logic

```python
import pandas as pd
import numpy as np
from typing import List, Optional
from dataclasses import dataclass

@dataclass
class ATRCalculation:
    """ATR calculation result."""
    atr_value: float
    period: int
    calculated_at: datetime
    confidence: float  # 0.0 to 1.0
    data_points: int

class ATRCalculator:
    """Calculates ATR-based stop loss levels."""
    
    def __init__(self, default_period: int = 14):
        self.default_period = default_period
        self.logger = logging.getLogger(__name__)
    
    async def calculate_atr(
        self,
        market_data: pd.DataFrame,
        period: Optional[int] = None
    ) -> ATRCalculation:
        """Calculate ATR from market data."""
        
        period = period or self.default_period
        
        if len(market_data) < period:
            raise ValueError(f"Insufficient data for ATR calculation. Need {period}, got {len(market_data)}")
        
        # Calculate True Range
        high = market_data['high']
        low = market_data['low']
        close = market_data['close'].shift(1)
        
        tr1 = high - low
        tr2 = abs(high - close)
        tr3 = abs(low - close)
        
        true_range = pd.DataFrame({
            'tr1': tr1,
            'tr2': tr2,
            'tr3': tr3
        }).max(axis=1)
        
        # Calculate ATR as SMA of True Range
        atr_value = true_range.rolling(window=period).mean().iloc[-1]
        
        # Calculate confidence based on data quality
        confidence = min(1.0, len(market_data) / (period * 2))
        
        return ATRCalculation(
            atr_value=float(atr_value),
            period=period,
            calculated_at=datetime.now(),
            confidence=confidence,
            data_points=len(market_data)
        )
    
    async def calculate_stop_loss(
        self,
        entry_price: float,
        atr_value: float,
        atr_multiplier: float,
        side: str
    ) -> float:
        """Calculate stop loss price based on ATR."""
        
        stop_distance = atr_value * atr_multiplier
        
        if side.lower() == 'buy':
            # For long positions, stop loss is below entry
            stop_loss = entry_price - stop_distance
        else:
            # For short positions, stop loss is above entry
            stop_loss = entry_price + stop_distance
        
        self.logger.info(
            f"Calculated stop loss: {stop_loss:.4f} "
            f"(entry: {entry_price:.4f}, ATR: {atr_value:.4f}, multiplier: {atr_multiplier})"
        )
        
        return stop_loss
```

### ATR-Based Stop Loss Strategies

```python
class ATRStopLossStrategies:
    """Different ATR-based stop loss strategies."""
    
    @staticmethod
    async def fixed_atr_multiplier(
        entry_price: float,
        atr_value: float,
        multiplier: float,
        side: str
    ) -> float:
        """Fixed ATR multiplier strategy."""
        return await ATRCalculator().calculate_stop_loss(
            entry_price, atr_value, multiplier, side
        )
    
    @staticmethod
    async def adaptive_atr_multiplier(
        entry_price: float,
        atr_value: float,
        base_multiplier: float,
        volatility_factor: float,
        side: str
    ) -> float:
        """Adaptive ATR multiplier based on volatility."""
        
        # Adjust multiplier based on volatility
        adjusted_multiplier = base_multiplier * (1 + volatility_factor)
        
        return await ATRCalculator().calculate_stop_loss(
            entry_price, atr_value, adjusted_multiplier, side
        )
    
    @staticmethod
    async def trailing_atr_stop(
        current_price: float,
        atr_value: float,
        multiplier: float,
        side: str,
        current_stop: Optional[float] = None
    ) -> float:
        """Trailing stop loss based on ATR."""
        
        stop_distance = atr_value * multiplier
        
        if side.lower() == 'buy':
            # For long positions, trail upward
            new_stop = current_price - stop_distance
            if current_stop is None or new_stop > current_stop:
                return new_stop
            else:
                return current_stop
        else:
            # For short positions, trail downward
            new_stop = current_price + stop_distance
            if current_stop is None or new_stop < current_stop:
                return new_stop
            else:
                return current_stop
```

## Integration with Risk Management

### Risk Limit Validation

```python
class ATRRiskValidator:
    """Validates ATR-based stops against risk limits."""
    
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(__name__)
    
    async def validate_stop_loss(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        quantity: float
    ) -> Tuple[bool, str]:
        """Validate stop loss against risk limits."""
        
        # Calculate risk per unit
        risk_per_unit = abs(entry_price - stop_loss)
        
        # Calculate total risk
        total_risk = risk_per_unit * quantity
        
        # Check against risk limits
        max_risk_per_trade = self.risk_manager.account_balance * self.risk_manager.limits.risk_per_trade
        
        if total_risk > max_risk_per_trade:
            return False, f"Stop loss risk (${total_risk:.2f}) exceeds max per trade (${max_risk_per_trade:.2f})"
        
        # Check position size limits
        position_value = entry_price * quantity
        max_position_value = self.risk_manager.account_balance * self.risk_manager.limits.max_position_size
        
        if position_value > max_position_value:
            return False, f"Position value (${position_value:.2f}) exceeds max position size (${max_position_value:.2f})"
        
        return True, "Stop loss validation passed"
    
    async def adjust_stop_loss_for_risk(
        self,
        symbol: str,
        entry_price: float,
        desired_stop_loss: float,
        quantity: float
    ) -> float:
        """Adjust stop loss to fit within risk limits."""
        
        max_risk_per_trade = self.risk_manager.account_balance * self.risk_manager.limits.risk_per_trade
        max_risk_per_unit = max_risk_per_trade / quantity
        
        if abs(entry_price - desired_stop_loss) <= max_risk_per_unit:
            return desired_stop_loss
        
        # Adjust stop loss to fit risk limits
        if entry_price > desired_stop_loss:  # Long position
            adjusted_stop = entry_price - max_risk_per_unit
        else:  # Short position
            adjusted_stop = entry_price + max_risk_per_unit
        
        self.logger.warning(
            f"Adjusted stop loss from {desired_stop_loss:.4f} to {adjusted_stop:.4f} "
            f"to fit risk limits"
        )
        
        return adjusted_stop
```

## ATR Data Management

### Historical ATR Storage

```python
class ATRDataManager:
    """Manages ATR calculation data and caching."""
    
    def __init__(self, storage_backend):
        self.storage_backend = storage_backend
        self.atr_cache: Dict[str, ATRCalculation] = {}
        self.cache_ttl_seconds = 300  # 5 minutes
        self.logger = logging.getLogger(__name__)
    
    async def get_atr_for_symbol(
        self,
        symbol: str,
        period: int = 14
    ) -> ATRCalculation:
        """Get ATR for symbol with caching."""
        
        cache_key = f"{symbol}_{period}"
        
        # Check cache first
        if cache_key in self.atr_cache:
            cached_atr = self.atr_cache[cache_key]
            if (datetime.now() - cached_atr.calculated_at).seconds < self.cache_ttl_seconds:
                return cached_atr
        
        # Calculate new ATR
        market_data = await self.storage_backend.get_market_data(symbol, period * 2)
        atr_calculator = ATRCalculator()
        atr_calculation = await atr_calculator.calculate_atr(market_data, period)
        
        # Cache result
        self.atr_cache[cache_key] = atr_calculation
        
        return atr_calculation
    
    async def update_atr_cache(
        self,
        symbol: str,
        new_atr: ATRCalculation
    ) -> None:
        """Update ATR cache with new calculation."""
        
        cache_key = f"{symbol}_{new_atr.period}"
        self.atr_cache[cache_key] = new_atr
        
        self.logger.debug(f"Updated ATR cache for {symbol}: {new_atr.atr_value:.4f}")
```

## Error Handling and Fallbacks

### ATR Calculation Failures

```python
class ATRFallbackManager:
    """Handles ATR calculation failures with fallbacks."""
    
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(__name__)
    
    async def calculate_stop_loss_with_fallback(
        self,
        symbol: str,
        entry_price: float,
        side: str,
        atr_value: Optional[float] = None
    ) -> float:
        """Calculate stop loss with fallback strategies."""
        
        try:
            if atr_value is None:
                # Try to get ATR from data manager
                atr_data_manager = ATRDataManager(self.storage_backend)
                atr_calculation = await atr_data_manager.get_atr_for_symbol(symbol)
                atr_value = atr_calculation.atr_value
            
            # Use ATR-based calculation
            atr_calculator = ATRCalculator()
            return await atr_calculator.calculate_stop_loss(
                entry_price, atr_value, self.risk_manager.limits.atr_multiplier, side
            )
            
        except Exception as e:
            self.logger.warning(f"ATR calculation failed for {symbol}: {e}")
            return await self._fallback_percentage_stop(entry_price, side)
    
    async def _fallback_percentage_stop(
        self,
        entry_price: float,
        side: str
    ) -> float:
        """Fallback to fixed percentage stop loss."""
        
        # Use 2% stop loss as fallback
        stop_percentage = 0.02
        
        if side.lower() == 'buy':
            return entry_price * (1 - stop_percentage)
        else:
            return entry_price * (1 + stop_percentage)
```

## Configuration

```yaml
atr_settings:
  default_period: 14
  cache_ttl_seconds: 300
  fallback_percentage: 0.02
  min_data_points: 20
  confidence_threshold: 0.7
  max_atr_multiplier: 5.0
  min_atr_multiplier: 0.5
```

## Testing Strategy

### Unit Tests
- ATR calculation accuracy
- Stop loss price calculations
- Risk limit validation
- Fallback mechanisms

### Integration Tests
- ATR data management
- Risk manager integration
- Error handling scenarios
- Performance with large datasets

### Performance Tests
- ATR calculation speed
- Cache efficiency
- Memory usage with multiple symbols
- Concurrent ATR calculations
