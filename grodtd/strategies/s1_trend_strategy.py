"""
S1 Trend Strategy Implementation.

This module implements the S1 trend-following strategy that generates
buy/sell signals based on VWAP and EMA trend detection from Story 1.1.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from grodtd.features.indicators import TrendDetector
from grodtd.storage.interfaces import OHLCVBar
from grodtd.strategies.base import BaseStrategy, Signal, StrategyState


@dataclass
class TrendSignal:
    """Represents a trend-based trading signal."""
    symbol: str
    side: str  # 'buy' or 'sell'
    strength: float  # Signal strength (0.0 to 1.0)
    price: float
    vwap: float
    ema: float
    trend: str
    stop_loss: float | None = None
    take_profit: float | None = None
    timestamp: datetime = None
    metadata: dict[str, Any] | None = None


class S1TrendStrategy(BaseStrategy):
    """
    S1 Trend-Following Strategy.
    
    Generates buy signals when price > VWAP AND price > EMA (uptrend).
    Generates sell signals when price < VWAP AND price < EMA (downtrend).
    """

    def __init__(self, symbol: str, config: dict[str, Any]):
        super().__init__("S1TrendStrategy", symbol, config)
        self.trend_detector = TrendDetector(symbol, ema_period=config.get('ema_period', 9))
        self.last_signal_side: str | None = None
        self.signal_cooldown_seconds = config.get('signal_cooldown_seconds', 60)
        self.last_signal_time: datetime | None = None

        # Signal strength calculation parameters
        self.min_signal_strength = config.get('min_signal_strength', 0.6)
        self.strength_calculation_method = config.get('strength_method', 'distance')

        self.logger.info(f"Initialized S1TrendStrategy for {symbol}")

    async def prepare(self, state: StrategyState) -> None:
        """
        Prepare strategy for signal generation.
        
        Updates the trend detector with the latest market data.
        """
        if state.market_data is not None and not state.market_data.empty:
            # Get the latest bar from market data
            latest_bar = self._get_latest_bar(state.market_data)
            if latest_bar:
                # Update trend detector with latest bar
                self.trend_detector.update(latest_bar)
                self.logger.debug(f"Updated trend detector with latest bar: {latest_bar.close}")

    async def generate_signals(self, state: StrategyState) -> list[Signal]:
        """
        Generate trading signals based on current trend.
        
        Returns:
            List of trading signals
        """
        signals = []

        if not self.is_enabled():
            return signals

        # Get current trend and indicators
        current_indicators = self.trend_detector.get_current_indicators()
        current_price = state.current_price
        current_trend = current_indicators.get('trend')
        vwap = current_indicators.get('vwap', 0)
        ema = current_indicators.get('ema')

        if not current_trend or vwap == 0 or ema is None:
            self.logger.debug("Trend indicators not ready, skipping signal generation")
            return signals

        # Check for signal cooldown
        if self._is_in_cooldown():
            self.logger.debug("Signal cooldown active, skipping signal generation")
            return signals

        # Generate buy signal for uptrend
        if current_trend == "up" and self._should_generate_buy_signal(current_price, vwap, ema):
            signal = self._create_buy_signal(current_price, vwap, ema, current_trend)
            if signal:
                signals.append(signal)
                self.last_signal_side = "buy"
                self.last_signal_time = datetime.now()
                self.logger.info(f"Generated BUY signal: {signal.symbol} @ {signal.price}")

        # Generate sell signal for downtrend
        elif current_trend == "down" and self._should_generate_sell_signal(current_price, vwap, ema):
            signal = self._create_sell_signal(current_price, vwap, ema, current_trend)
            if signal:
                signals.append(signal)
                self.last_signal_side = "sell"
                self.last_signal_time = datetime.now()
                self.logger.info(f"Generated SELL signal: {signal.symbol} @ {signal.price}")

        return signals

    async def on_fill(self, signal: Signal, fill_data: dict[str, Any]) -> None:
        """
        Handle order fill event.
        
        Updates strategy state when a signal is filled.
        """
        self.logger.info(f"Signal filled: {signal.symbol} {signal.side} @ {fill_data.get('price', 'N/A')}")

        # Reset signal tracking
        self.last_signal_side = None
        self.last_signal_time = None

    def _get_latest_bar(self, market_data) -> OHLCVBar | None:
        """Extract the latest bar from market data."""
        try:
            if hasattr(market_data, 'iloc'):
                # pandas DataFrame
                latest_row = market_data.iloc[-1]
                return OHLCVBar(
                    timestamp=latest_row.get('timestamp', datetime.now()),
                    open=latest_row.get('open', 0),
                    high=latest_row.get('high', 0),
                    low=latest_row.get('low', 0),
                    close=latest_row.get('close', 0),
                    volume=latest_row.get('volume', 0)
                )
        except Exception as e:
            self.logger.error(f"Error extracting latest bar: {e}")

        return None

    def _should_generate_buy_signal(self, price: float, vwap: float, ema: float) -> bool:
        """Check if a buy signal should be generated."""
        # Basic trend condition: price > VWAP AND price > EMA
        trend_condition = price > vwap and price > ema

        # Avoid duplicate signals
        no_duplicate = self.last_signal_side != "buy"

        return trend_condition and no_duplicate

    def _should_generate_sell_signal(self, price: float, vwap: float, ema: float) -> bool:
        """Check if a sell signal should be generated."""
        # Basic trend condition: price < VWAP AND price < EMA
        trend_condition = price < vwap and price < ema

        # Avoid duplicate signals
        no_duplicate = self.last_signal_side != "sell"

        return trend_condition and no_duplicate

    def _create_buy_signal(self, price: float, vwap: float, ema: float, trend: str) -> Signal | None:
        """Create a buy signal."""
        strength = self._calculate_signal_strength(price, vwap, ema, "buy")

        if strength < self.min_signal_strength:
            self.logger.debug(f"Buy signal strength {strength:.3f} below minimum {self.min_signal_strength}")
            return None

        return Signal(
            symbol=self.symbol,
            side="buy",
            strength=strength,
            price=price,
            stop_loss=self._calculate_stop_loss(price, vwap, ema, "buy"),
            take_profit=self._calculate_take_profit(price, vwap, ema, "buy"),
            timestamp=datetime.now(),
            metadata={
                "strategy": "S1TrendStrategy",
                "trend": trend,
                "vwap": vwap,
                "ema": ema,
                "signal_type": "trend_following"
            }
        )

    def _create_sell_signal(self, price: float, vwap: float, ema: float, trend: str) -> Signal | None:
        """Create a sell signal."""
        strength = self._calculate_signal_strength(price, vwap, ema, "sell")

        if strength < self.min_signal_strength:
            self.logger.debug(f"Sell signal strength {strength:.3f} below minimum {self.min_signal_strength}")
            return None

        return Signal(
            symbol=self.symbol,
            side="sell",
            strength=strength,
            price=price,
            stop_loss=self._calculate_stop_loss(price, vwap, ema, "sell"),
            take_profit=self._calculate_take_profit(price, vwap, ema, "sell"),
            timestamp=datetime.now(),
            metadata={
                "strategy": "S1TrendStrategy",
                "trend": trend,
                "vwap": vwap,
                "ema": ema,
                "signal_type": "trend_following"
            }
        )

    def _calculate_signal_strength(self, price: float, vwap: float, ema: float, side: str) -> float:
        """Calculate signal strength based on distance from indicators."""
        if self.strength_calculation_method == "distance":
            if side == "buy":
                # Strength based on how far price is above both indicators
                vwap_distance = (price - vwap) / vwap if vwap > 0 else 0
                ema_distance = (price - ema) / ema if ema > 0 else 0
                # Use the minimum distance to avoid over-optimistic signals
                strength = min(vwap_distance, ema_distance) * 10  # Scale factor
            else:  # sell
                # Strength based on how far price is below both indicators
                vwap_distance = (vwap - price) / vwap if vwap > 0 else 0
                ema_distance = (ema - price) / ema if ema > 0 else 0
                # Use the minimum distance to avoid over-optimistic signals
                strength = min(vwap_distance, ema_distance) * 10  # Scale factor

            # Normalize to 0-1 range
            return max(0.0, min(1.0, strength))

        # Default strength calculation
        return 0.8

    def _calculate_stop_loss(self, price: float, vwap: float, ema: float, side: str) -> float | None:
        """Calculate stop loss based on ATR or indicator levels."""
        # Simple stop loss: 2% below/above entry price
        stop_percentage = 0.02

        if side == "buy":
            return price * (1 - stop_percentage)
        else:  # sell
            return price * (1 + stop_percentage)

    def _calculate_take_profit(self, price: float, vwap: float, ema: float, side: str) -> float | None:
        """Calculate take profit based on risk-reward ratio."""
        # Simple take profit: 2:1 risk-reward ratio
        profit_percentage = 0.04  # 4% profit for 2% risk

        if side == "buy":
            return price * (1 + profit_percentage)
        else:  # sell
            return price * (1 - profit_percentage)

    def _is_in_cooldown(self) -> bool:
        """Check if strategy is in signal cooldown period."""
        if not self.last_signal_time:
            return False

        time_since_last_signal = (datetime.now() - self.last_signal_time).total_seconds()
        return time_since_last_signal < self.signal_cooldown_seconds

    def get_strategy_state(self) -> dict[str, Any]:
        """Get current strategy state for monitoring."""
        indicators = self.trend_detector.get_current_indicators()

        return {
            "strategy_name": self.name,
            "symbol": self.symbol,
            "enabled": self.is_enabled(),
            "current_trend": indicators.get('trend'),
            "vwap": indicators.get('vwap'),
            "ema": indicators.get('ema'),
            "last_price": indicators.get('last_price'),
            "last_signal_side": self.last_signal_side,
            "last_signal_time": self.last_signal_time,
            "in_cooldown": self._is_in_cooldown()
        }


# Factory function for creating S1 strategy
def create_s1_trend_strategy(symbol: str, config: dict[str, Any]) -> S1TrendStrategy:
    """Create a new S1 trend strategy instance."""
    return S1TrendStrategy(symbol, config)
