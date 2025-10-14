"""
Unit tests for technical indicators.
"""

import pytest
import pandas as pd
import numpy as np
from grodtd.features.indicators import TechnicalIndicators


class TestTechnicalIndicators:
    """Test cases for TechnicalIndicators."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.indicators = TechnicalIndicators()
        
        # Create sample OHLCV data
        dates = pd.date_range('2023-01-01', periods=100, freq='1H')
        np.random.seed(42)
        
        # Generate realistic price data
        base_price = 100.0
        returns = np.random.normal(0, 0.01, 100)
        prices = [base_price]
        
        for ret in returns[1:]:
            prices.append(prices[-1] * (1 + ret))
        
        self.sample_data = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.005))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.005))) for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        })
        self.sample_data.set_index('timestamp', inplace=True)
    
    def test_calculate_ema(self):
        """Test EMA calculation."""
        ema = self.indicators.calculate_ema(self.sample_data['close'], 20)
        
        assert len(ema) == len(self.sample_data)
        assert not ema.iloc[:19].notna().all()  # First 19 values should be NaN
        assert ema.iloc[19:].notna().all()  # Rest should be valid
    
    def test_calculate_rsi(self):
        """Test RSI calculation."""
        rsi = self.indicators.calculate_rsi(self.sample_data['close'], 14)
        
        assert len(rsi) == len(self.sample_data)
        assert rsi.min() >= 0
        assert rsi.max() <= 100
        assert not rsi.iloc[:13].notna().all()  # First 13 values should be NaN
    
    def test_calculate_atr(self):
        """Test ATR calculation."""
        atr = self.indicators.calculate_atr(self.sample_data, 14)
        
        assert len(atr) == len(self.sample_data)
        assert atr.min() >= 0  # ATR should be non-negative
        assert not atr.iloc[:13].notna().all()  # First 13 values should be NaN
    
    def test_calculate_vwap(self):
        """Test VWAP calculation."""
        vwap = self.indicators.calculate_vwap(self.sample_data, 20)
        
        assert len(vwap) == len(self.sample_data)
        assert not vwap.iloc[:19].notna().all()  # First 19 values should be NaN
        assert vwap.iloc[19:].notna().all()  # Rest should be valid
    
    def test_calculate_bollinger_bands(self):
        """Test Bollinger Bands calculation."""
        upper, middle, lower = self.indicators.calculate_bollinger_bands(
            self.sample_data['close'], 20, 2.0
        )
        
        assert len(upper) == len(self.sample_data)
        assert len(middle) == len(self.sample_data)
        assert len(lower) == len(self.sample_data)
        
        # Upper band should be above middle, lower should be below
        valid_mask = middle.notna()
        assert (upper[valid_mask] >= middle[valid_mask]).all()
        assert (lower[valid_mask] <= middle[valid_mask]).all()
    
    def test_calculate_macd(self):
        """Test MACD calculation."""
        macd, signal, histogram = self.indicators.calculate_macd(
            self.sample_data['close'], 12, 26, 9
        )
        
        assert len(macd) == len(self.sample_data)
        assert len(signal) == len(self.sample_data)
        assert len(histogram) == len(self.sample_data)
        
        # Histogram should be MACD - Signal
        valid_mask = macd.notna() & signal.notna()
        expected_histogram = macd[valid_mask] - signal[valid_mask]
        assert np.allclose(histogram[valid_mask], expected_histogram, rtol=1e-10)
    
    def test_calculate_all_features(self):
        """Test calculation of all features."""
        result = self.indicators.calculate_all_features(
            self.sample_data,
            vwap_period=20,
            ema_fast=9,
            ema_slow=20,
            atr_period=14,
            rsi_period=14
        )
        
        # Check that all expected columns are present
        expected_columns = [
            'vwap', 'ema_fast', 'ema_slow', 'atr', 'rsi',
            'bb_upper', 'bb_middle', 'bb_lower',
            'macd', 'macd_signal', 'macd_histogram'
        ]
        
        for col in expected_columns:
            assert col in result.columns
        
        # Check that original data is preserved
        original_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in original_columns:
            assert col in result.columns
            assert result[col].equals(self.sample_data[col])
    
    def test_invalid_data_handling(self):
        """Test handling of invalid data."""
        # Test with missing columns
        invalid_data = self.sample_data[['open', 'high']].copy()
        
        with pytest.raises(ValueError):
            self.indicators.calculate_vwap(invalid_data, 20)
        
        with pytest.raises(ValueError):
            self.indicators.calculate_atr(invalid_data, 14)
    
    def test_edge_cases(self):
        """Test edge cases."""
        # Test with very small dataset
        small_data = self.sample_data.iloc[:5].copy()
        
        # These should handle small datasets gracefully
        ema = self.indicators.calculate_ema(small_data['close'], 10)
        if ema is not None:
            assert len(ema) == len(small_data)
        
        # Test with all NaN values
        nan_data = self.sample_data.copy()
        nan_data['close'] = np.nan
        
        ema = self.indicators.calculate_ema(nan_data['close'], 20)
        assert ema.isna().all()
