"""
Technical indicators and feature calculation.

This module provides implementations of various technical indicators
including VWAP, EMA, ATR, RSI, and other commonly used trading indicators.
"""

import logging
from typing import Optional, Tuple
import pandas as pd
import numpy as np
import pandas_ta as ta


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
