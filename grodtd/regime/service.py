"""
Regime state service for providing regime information to strategy modules.

This service acts as a central registry for regime classifiers and provides
a unified interface for accessing current regime states.
"""

import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import threading
import time
from .classifier import RegimeClassifier, RegimeType, RegimeConfig
from grodtd.storage.interfaces import OHLCVBar


class RegimeStateService:
    """
    Central service for managing regime classification across all symbols.
    
    This service provides a unified interface for strategy modules to access
    current regime states and ensures regime classification is updated every 5 minutes.
    """
    
    def __init__(self, config: Optional[RegimeConfig] = None):
        self.config = config or RegimeConfig()
        self.logger = logging.getLogger(__name__)
        
        # Registry of classifiers by symbol
        self._classifiers: Dict[str, RegimeClassifier] = {}
        
        # Current regime states by symbol
        self._current_regimes: Dict[str, RegimeType] = {}
        self._regime_confidence: Dict[str, float] = {}
        self._last_update_times: Dict[str, datetime] = {}
        
        # Threading for periodic updates
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # Update interval (5 minutes)
        self._update_interval = 300  # 5 minutes in seconds
        
        self.logger.info("RegimeStateService initialized")
    
    def register_symbol(self, symbol: str) -> RegimeClassifier:
        """
        Register a symbol for regime classification.
        
        Args:
            symbol: Symbol to register
            
        Returns:
            RegimeClassifier instance for the symbol
        """
        with self._lock:
            if symbol not in self._classifiers:
                self._classifiers[symbol] = RegimeClassifier(symbol, self.config)
                self.logger.info(f"Registered symbol {symbol} for regime classification")
            
            return self._classifiers[symbol]
    
    def update_regime(self, symbol: str, bar: OHLCVBar) -> RegimeType:
        """
        Update regime classification for a symbol with new market data.
        
        Args:
            symbol: Symbol to update
            bar: New market data bar
            
        Returns:
            Current regime for the symbol
        """
        with self._lock:
            # Ensure symbol is registered
            if symbol not in self._classifiers:
                self.register_symbol(symbol)
            
            # Update regime classification
            classifier = self._classifiers[symbol]
            regime = classifier.update(bar)
            
            # Update service state
            self._current_regimes[symbol] = regime
            self._regime_confidence[symbol] = classifier.get_classification_confidence()
            self._last_update_times[symbol] = datetime.now()
            
            self.logger.debug(f"Updated regime for {symbol}: {regime.value}")
            
            return regime
    
    def get_current_regime(self, symbol: str) -> Optional[RegimeType]:
        """
        Get the current regime for a symbol.
        
        Args:
            symbol: Symbol to query
            
        Returns:
            Current regime or None if not available
        """
        with self._lock:
            return self._current_regimes.get(symbol)
    
    def get_regime_confidence(self, symbol: str) -> float:
        """
        Get the confidence of the current regime classification.
        
        Args:
            symbol: Symbol to query
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        with self._lock:
            return self._regime_confidence.get(symbol, 0.0)
    
    def get_last_update_time(self, symbol: str) -> Optional[datetime]:
        """
        Get the last update time for a symbol's regime.
        
        Args:
            symbol: Symbol to query
            
        Returns:
            Last update time or None if not available
        """
        with self._lock:
            return self._last_update_times.get(symbol)
    
    def get_all_regimes(self) -> Dict[str, RegimeType]:
        """
        Get current regimes for all registered symbols.
        
        Returns:
            Dictionary mapping symbols to their current regimes
        """
        with self._lock:
            return self._current_regimes.copy()
    
    def get_regime_summary(self) -> Dict[str, Dict]:
        """
        Get a comprehensive summary of all regime states.
        
        Returns:
            Dictionary with regime information for all symbols
        """
        with self._lock:
            summary = {}
            for symbol in self._classifiers.keys():
                summary[symbol] = {
                    'regime': self._current_regimes.get(symbol),
                    'confidence': self._regime_confidence.get(symbol, 0.0),
                    'last_update': self._last_update_times.get(symbol),
                    'classifier_ready': symbol in self._classifiers
                }
            return summary
    
    def is_regime_stale(self, symbol: str, max_age_minutes: int = 10) -> bool:
        """
        Check if a symbol's regime data is stale.
        
        Args:
            symbol: Symbol to check
            max_age_minutes: Maximum age in minutes before considering stale
            
        Returns:
            True if regime data is stale
        """
        with self._lock:
            last_update = self._last_update_times.get(symbol)
            if last_update is None:
                return True
            
            age = datetime.now() - last_update
            return age > timedelta(minutes=max_age_minutes)
    
    def get_stale_symbols(self, max_age_minutes: int = 10) -> List[str]:
        """
        Get list of symbols with stale regime data.
        
        Args:
            max_age_minutes: Maximum age in minutes before considering stale
            
        Returns:
            List of symbols with stale data
        """
        with self._lock:
            stale_symbols = []
            for symbol in self._classifiers.keys():
                if self.is_regime_stale(symbol, max_age_minutes):
                    stale_symbols.append(symbol)
            return stale_symbols
    
    def start_periodic_updates(self):
        """Start the periodic update thread."""
        if self._update_thread is None or not self._update_thread.is_alive():
            self._stop_event.clear()
            self._update_thread = threading.Thread(target=self._periodic_update_loop, daemon=True)
            self._update_thread.start()
            self.logger.info("Started periodic regime updates")
    
    def stop_periodic_updates(self):
        """Stop the periodic update thread."""
        if self._update_thread and self._update_thread.is_alive():
            self._stop_event.set()
            self._update_thread.join(timeout=5)
            self.logger.info("Stopped periodic regime updates")
    
    def _periodic_update_loop(self):
        """Background thread for periodic regime updates."""
        while not self._stop_event.is_set():
            try:
                # Check for stale regimes and log warnings
                stale_symbols = self.get_stale_symbols()
                if stale_symbols:
                    self.logger.warning(f"Stale regime data for symbols: {stale_symbols}")
                
                # Sleep until next update cycle
                self._stop_event.wait(self._update_interval)
                
            except Exception as e:
                self.logger.error(f"Error in periodic regime update: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def reset_symbol(self, symbol: str):
        """
        Reset regime classification for a symbol.
        
        Args:
            symbol: Symbol to reset
        """
        with self._lock:
            if symbol in self._classifiers:
                self._classifiers[symbol].reset()
                self._current_regimes.pop(symbol, None)
                self._regime_confidence.pop(symbol, None)
                self._last_update_times.pop(symbol, None)
                self.logger.info(f"Reset regime classification for {symbol}")
    
    def reset_all(self):
        """Reset all regime classifications."""
        with self._lock:
            for classifier in self._classifiers.values():
                classifier.reset()
            self._current_regimes.clear()
            self._regime_confidence.clear()
            self._last_update_times.clear()
            self.logger.info("Reset all regime classifications")
    
    def get_classifier(self, symbol: str) -> Optional[RegimeClassifier]:
        """
        Get the classifier instance for a symbol.
        
        Args:
            symbol: Symbol to get classifier for
            
        Returns:
            RegimeClassifier instance or None if not registered
        """
        with self._lock:
            return self._classifiers.get(symbol)
    
    def get_registered_symbols(self) -> List[str]:
        """
        Get list of all registered symbols.
        
        Returns:
            List of registered symbols
        """
        with self._lock:
            return list(self._classifiers.keys())
    
    def __del__(self):
        """Cleanup when service is destroyed."""
        self.stop_periodic_updates()


# Global service instance
_regime_service: Optional[RegimeStateService] = None


def get_regime_service() -> RegimeStateService:
    """
    Get the global regime state service instance.
    
    Returns:
        Global RegimeStateService instance
    """
    global _regime_service
    if _regime_service is None:
        _regime_service = RegimeStateService()
    return _regime_service


def initialize_regime_service(config: Optional[RegimeConfig] = None) -> RegimeStateService:
    """
    Initialize the global regime state service.
    
    Args:
        config: Optional configuration for the service
        
    Returns:
        Initialized RegimeStateService instance
    """
    global _regime_service
    _regime_service = RegimeStateService(config)
    return _regime_service
