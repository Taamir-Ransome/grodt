"""
Market regime classification module.

This module provides functionality to classify market regimes based on
volatility, momentum, and price action data.
"""

from .classifier import RegimeClassifier, RegimeType, RegimeConfig, RegimeFeatures
from .service import RegimeStateService, get_regime_service
from .integration import RegimeIndicatorIntegration, RegimeIntegrationManager, get_integration_manager

__all__ = [
    'RegimeClassifier', 
    'RegimeType', 
    'RegimeConfig', 
    'RegimeFeatures',
    'RegimeStateService', 
    'get_regime_service',
    'RegimeIndicatorIntegration',
    'RegimeIntegrationManager',
    'get_integration_manager'
]
