"""
Technical indicators and feature calculation.

This module provides implementations of various technical indicators
including VWAP, EMA, ATR, RSI, and other commonly used trading indicators.
"""

import logging
from typing import Optional, Tuple, List
import pandas as pd
import numpy as np
import pandas_ta as ta
from grodtd.storage.interfaces import OHLCVBar


class VWAPCalculator:
    """Real-time VWAP calculator that updates with each new bar."""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.logger = logging.getLogger(__name__)
        self._cumulative_volume = 0.0
        self._cumulative_volume_price = 0.0
        self._current_vwap = 0.0
        self._bars_count = 0
    
    def update(self, bar: OHLCVBar) -> float:
        """Update VWAP with a new bar and return current VWAP value."""
        # Validate input data
        if bar.volume < 0:
            self.logger.warning(f"Negative volume detected for {self.symbol}: {bar.volume}")
            return self._current_vwap
        
        # Calculate typical price (HLC/3)
        typical_price = (bar.high + bar.low + bar.close) / 3
        
        # Update cumulative values
        self._cumulative_volume += bar.volume
        self._cumulative_volume_price += typical_price * bar.volume
        
        # Calculate new VWAP
        if self._cumulative_volume > 0:
            self._current_vwap = self._cumulative_volume_price / self._cumulative_volume
        else:
            self.logger.warning(f"Zero cumulative volume for {self.symbol}")
        
        self._bars_count += 1
        self.logger.debug(f"VWAP updated for {self.symbol}: {self._current_vwap:.4f}")
        
        return self._current_vwap
    
    def get_current_vwap(self) -> float:
        """Get the current VWAP value."""
        return self._current_vwap
    
    def reset(self):
        """Reset the VWAP calculation."""
        self._cumulative_volume = 0.0
        self._cumulative_volume_price = 0.0
        self._current_vwap = 0.0
        self._bars_count = 0
        self.logger.info(f"VWAP reset for {self.symbol}")


class EMACalculator:
    """Real-time EMA calculator that updates with each new bar."""
    
    def __init__(self, symbol: str, period: int = 9):
        self.symbol = symbol
        self.period = period
        self.logger = logging.getLogger(__name__)
        self._alpha = 2.0 / (period + 1)
        self._current_ema = None
        self._bars_count = 0
    
    def update(self, price: float) -> float:
        """Update EMA with a new price and return current EMA value."""
        # Validate input data
        if price <= 0:
            self.logger.warning(f"Invalid price for {self.symbol}: {price}")
            return self._current_ema or 0.0
        
        if self._current_ema is None:
            # First value - use price as initial EMA
            self._current_ema = price
        else:
            # EMA calculation: EMA = α * price + (1 - α) * previous_EMA
            self._current_ema = self._alpha * price + (1 - self._alpha) * self._current_ema
        
        self._bars_count += 1
        self.logger.debug(f"EMA({self.period}) updated for {self.symbol}: {self._current_ema:.4f}")
        
        return self._current_ema
    
    def get_current_ema(self) -> Optional[float]:
        """Get the current EMA value."""
        return self._current_ema
    
    def reset(self):
        """Reset the EMA calculation."""
        self._current_ema = None
        self._bars_count = 0
        self.logger.info(f"EMA({self.period}) reset for {self.symbol}")


class TrendDetector:
    """Detects trend direction based on price vs VWAP and EMA."""
    
    def __init__(self, symbol: str, ema_period: int = 9):
        self.symbol = symbol
        self.logger = logging.getLogger(__name__)
        self.vwap_calculator = VWAPCalculator(symbol)
        self.ema_calculator = EMACalculator(symbol, ema_period)
        self._current_trend = None
        self._last_price = None
    
    def update(self, bar: OHLCVBar) -> str:
        """Update trend detection with a new bar and return current trend."""
        # Update indicators
        vwap = self.vwap_calculator.update(bar)
        ema = self.ema_calculator.update(bar.close)
        
        # Determine trend
        trend = self._determine_trend(bar.close, vwap, ema)
        
        # Log trend changes
        if trend != self._current_trend:
            self.logger.info(f"Trend changed for {self.symbol}: {self._current_trend} -> {trend}")
            self._current_trend = trend
        
        self._last_price = bar.close
        return trend
    
    def _determine_trend(self, price: float, vwap: float, ema: Optional[float]) -> str:
        """Determine trend based on price vs VWAP and EMA."""
        if ema is None or vwap == 0:
            # EMA or VWAP not ready yet
            return "unknown"
        
        # Trend is "up" when price is above both VWAP and EMA
        if price > vwap and price > ema:
            return "up"
        # Trend is "down" when price is below both VWAP and EMA
        elif price < vwap and price < ema:
            return "down"
        # Otherwise, trend is "sideways" or "mixed"
        else:
            return "sideways"
    
    def get_current_trend(self) -> Optional[str]:
        """Get the current trend."""
        return self._current_trend
    
    def get_current_indicators(self) -> dict:
        """Get current indicator values."""
        return {
            'vwap': self.vwap_calculator.get_current_vwap(),
            'ema': self.ema_calculator.get_current_ema(),
            'trend': self._current_trend,
            'last_price': self._last_price
        }
    
    def reset(self):
        """Reset the trend detector."""
        self.vwap_calculator.reset()
        self.ema_calculator.reset()
        self._current_trend = None
        self._last_price = None
        self.logger.info(f"Trend detector reset for {self.symbol}")


class TechnicalIndicators:
    """Calculate technical indicators for market data."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def calculate_vwap(
        self, 
        data: pd.DataFrame, 
        period: int = 20,
        anchor: str = "D"
    ) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP).
        
        Args:
            data: DataFrame with OHLCV data
            period: Lookback period for VWAP
            anchor: Time anchor for VWAP (D for daily)
        
        Returns:
            Series with VWAP values
        """
        if 'volume' not in data.columns or 'close' not in data.columns:
            raise ValueError("Data must contain 'volume' and 'close' columns")
        
        # Calculate typical price (HLC/3)
        typical_price = (data['high'] + data['low'] + data['close']) / 3
        
        # Calculate VWAP
        vwap = (typical_price * data['volume']).rolling(window=period).sum() / data['volume'].rolling(window=period).sum()
        
        return vwap
    
    def calculate_ema(
        self, 
        data: pd.Series, 
        period: int
    ) -> pd.Series:
        """
        Calculate Exponential Moving Average (EMA).
        
        Args:
            data: Price series
            period: EMA period
        
        Returns:
            Series with EMA values
        """
        return ta.ema(data, length=period)
    
    def calculate_atr(
        self, 
        data: pd.DataFrame, 
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        
        Args:
            data: DataFrame with OHLC data
            period: ATR period
        
        Returns:
            Series with ATR values
        """
        if not all(col in data.columns for col in ['high', 'low', 'close']):
            raise ValueError("Data must contain 'high', 'low', and 'close' columns")
        
        return ta.atr(data['high'], data['low'], data['close'], length=period)
    
    def calculate_rsi(
        self, 
        data: pd.Series, 
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            data: Price series
            period: RSI period
        
        Returns:
            Series with RSI values
        """
        return ta.rsi(data, length=period)
    
    def calculate_bollinger_bands(
        self, 
        data: pd.Series, 
        period: int = 20, 
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Args:
            data: Price series
            period: Moving average period
            std_dev: Standard deviation multiplier
        
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        bb = ta.bbands(data, length=period, std=std_dev)
        # Get the column names dynamically
        upper_col = [col for col in bb.columns if col.startswith('BBU')][0]
        middle_col = [col for col in bb.columns if col.startswith('BBM')][0]
        lower_col = [col for col in bb.columns if col.startswith('BBL')][0]
        return bb[upper_col], bb[middle_col], bb[lower_col]
    
    def calculate_macd(
        self, 
        data: pd.Series, 
        fast: int = 12, 
        slow: int = 26, 
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            data: Price series
            fast: Fast EMA period
            slow: Slow EMA period
            signal: Signal line EMA period
        
        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        macd = ta.macd(data, fast=fast, slow=slow, signal=signal)
        return macd['MACD_12_26_9'], macd['MACDs_12_26_9'], macd['MACDh_12_26_9']
    
    def calculate_all_features(
        self, 
        data: pd.DataFrame,
        vwap_period: int = 20,
        ema_fast: int = 9,
        ema_slow: int = 20,
        atr_period: int = 14,
        rsi_period: int = 14
    ) -> pd.DataFrame:
        """
        Calculate all technical indicators for the dataset.
        
        Args:
            data: DataFrame with OHLCV data
            vwap_period: VWAP period
            ema_fast: Fast EMA period
            ema_slow: Slow EMA period
            atr_period: ATR period
            rsi_period: RSI period
        
        Returns:
            DataFrame with original data plus all indicators
        """
        result = data.copy()
        
        try:
            # Calculate VWAP
            result['vwap'] = self.calculate_vwap(data, vwap_period)
            
            # Calculate EMAs
            result['ema_fast'] = self.calculate_ema(data['close'], ema_fast)
            result['ema_slow'] = self.calculate_ema(data['close'], ema_slow)
            
            # Calculate ATR
            result['atr'] = self.calculate_atr(data, atr_period)
            
            # Calculate RSI
            result['rsi'] = self.calculate_rsi(data['close'], rsi_period)
            
            # Calculate Bollinger Bands
            bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(data['close'])
            result['bb_upper'] = bb_upper
            result['bb_middle'] = bb_middle
            result['bb_lower'] = bb_lower
            
            # Calculate MACD
            macd_line, signal_line, histogram = self.calculate_macd(data['close'])
            result['macd'] = macd_line
            result['macd_signal'] = signal_line
            result['macd_histogram'] = histogram
            
            self.logger.info("Successfully calculated all technical indicators")
            
        except Exception as e:
            self.logger.error(f"Error calculating indicators: {e}")
            raise
        
        return result


# Factory function for creating indicators calculator
def create_indicators_calculator() -> TechnicalIndicators:
    """Create a new technical indicators calculator."""
    return TechnicalIndicators()
