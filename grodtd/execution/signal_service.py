"""
Trade Signal Service.

This module handles the processing of trading signals and their conversion
to executable orders through the execution engine.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from grodtd.connectors.robinhood import Order
from grodtd.execution.engine import ExecutionEngine, ExecutionResult
from grodtd.risk.manager import RiskManager
from grodtd.strategies.base import Signal


@dataclass
class SignalProcessingResult:
    """Result of signal processing."""
    signal: Signal
    order_id: str | None = None
    execution_result: ExecutionResult | None = None
    success: bool = False
    error_message: str | None = None


class TradeSignalService:
    """
    Service for processing trading signals and converting them to orders.

    This service acts as the bridge between strategy signals and the execution engine,
    handling signal validation, order creation, and execution coordination.
    """

    def __init__(self, execution_engine: ExecutionEngine, risk_manager: RiskManager):
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.logger = logging.getLogger(__name__)
        self.signal_callbacks: list[Callable] = []

        # Signal processing configuration
        self.max_concurrent_signals = 5
        self.signal_timeout_seconds = 30
        self.active_signals: dict[str, Signal] = {}

        self.logger.info("Initialized TradeSignalService")

    async def process_signal(self, signal: Signal) -> SignalProcessingResult:
        """
        Process a trading signal and convert it to an order.
        
        Args:
            signal: Trading signal to process
            
        Returns:
            SignalProcessingResult with processing details
        """
        self.logger.info(f"Processing signal: {signal.symbol} {signal.side} @ {signal.price}")

        try:
            # Validate signal
            validation_result = self._validate_signal(signal)
            if not validation_result["valid"]:
                return SignalProcessingResult(
                    signal=signal,
                    success=False,
                    error_message=validation_result["reason"]
                )

            # Check for conflicting signals
            if self._has_conflicting_signal(signal):
                return SignalProcessingResult(
                    signal=signal,
                    success=False,
                    error_message="Conflicting signal already active"
                )

            # Create order from signal
            order = self._create_order_from_signal(signal)
            if not order:
                return SignalProcessingResult(
                    signal=signal,
                    success=False,
                    error_message="Failed to create order from signal"
                )

            # Submit order to execution engine
            execution_result = await self.execution_engine.submit_order(order)

            # Track active signal
            if execution_result.status.value in ["acknowledged", "partial_filled"]:
                self.active_signals[signal.symbol] = signal

            # Trigger callbacks
            await self._trigger_signal_callbacks("signal_processed", signal, execution_result)

            return SignalProcessingResult(
                signal=signal,
                order_id=execution_result.order_id,
                execution_result=execution_result,
                success=execution_result.status.value in ["acknowledged", "partial_filled", "filled"],
                error_message=execution_result.error_message
            )

        except Exception as e:
            self.logger.error(f"Error processing signal: {e}")
            return SignalProcessingResult(
                signal=signal,
                success=False,
                error_message=str(e)
            )

    async def process_multiple_signals(self, signals: list[Signal]) -> list[SignalProcessingResult]:
        """
        Process multiple signals concurrently.
        
        Args:
            signals: List of signals to process
            
        Returns:
            List of processing results
        """
        self.logger.info(f"Processing {len(signals)} signals")

        results = []
        for signal in signals:
            result = await self.process_signal(signal)
            results.append(result)

        return results

    async def cancel_signal(self, symbol: str) -> bool:
        """
        Cancel active signal for a symbol.
        
        Args:
            symbol: Symbol to cancel signal for
            
        Returns:
            True if cancellation was successful
        """
        if symbol not in self.active_signals:
            self.logger.warning(f"No active signal found for {symbol}")
            return False

        # Remove from active signals
        signal = self.active_signals.pop(symbol)

        # Cancel any associated orders
        # Note: This would require tracking order IDs per signal
        # For now, we'll just log the cancellation
        self.logger.info(f"Cancelled signal for {symbol}")

        # Trigger callbacks
        await self._trigger_signal_callbacks("signal_cancelled", signal, None)

        return True

    def _validate_signal(self, signal: Signal) -> dict[str, Any]:
        """Validate a trading signal."""
        # Check signal strength
        if signal.strength < 0.5:
            return {"valid": False, "reason": "Signal strength too low"}

        # Check price validity
        if signal.price <= 0:
            return {"valid": False, "reason": "Invalid price"}

        # Check side validity
        if signal.side not in ["buy", "sell"]:
            return {"valid": False, "reason": "Invalid signal side"}

        # Check symbol validity
        if not signal.symbol or len(signal.symbol) == 0:
            return {"valid": False, "reason": "Invalid symbol"}

        return {"valid": True, "reason": "Signal is valid"}

    def _has_conflicting_signal(self, signal: Signal) -> bool:
        """Check if there's a conflicting signal for the same symbol."""
        if signal.symbol not in self.active_signals:
            return False

        existing_signal = self.active_signals[signal.symbol]

        # Check for opposite side signals
        if existing_signal.side != signal.side:
            self.logger.warning(f"Conflicting signal detected: {existing_signal.side} vs {signal.side}")
            return True

        return False

    def _create_order_from_signal(self, signal: Signal) -> Order | None:
        """Create an order from a trading signal."""
        try:
            # Generate unique order ID
            order_id = f"{signal.symbol}_{signal.side}_{int(datetime.now().timestamp())}"

            # Calculate position size using risk manager
            position_size = self._calculate_position_size(signal)
            if position_size <= 0:
                self.logger.warning(f"Invalid position size calculated: {position_size}")
                return None

            # Create order
            order = Order(
                id=order_id,
                symbol=signal.symbol,
                side=signal.side,
                quantity=position_size,
                price=signal.price,
                order_type="market",  # Market orders for trend following
                status="pending",
                created_at=datetime.now()
            )

            self.logger.info(f"Created order: {order.symbol} {order.side} {order.quantity} @ {order.price}")
            return order

        except Exception as e:
            self.logger.error(f"Error creating order from signal: {e}")
            return None

    def _calculate_position_size(self, signal: Signal) -> float:
        """Calculate position size based on risk management rules."""
        try:
            # Get current account balance
            risk_summary = self.risk_manager.get_risk_summary()
            account_balance = risk_summary.get("account_balance", 10000.0)  # Default fallback

            # Calculate stop loss distance
            stop_loss = signal.stop_loss or (signal.price * 0.98 if signal.side == "buy" else signal.price * 1.02)
            stop_distance = abs(signal.price - stop_loss)

            # Use risk manager to calculate position size
            position_size = self.risk_manager.calculate_position_size(
                symbol=signal.symbol,
                entry_price=signal.price,
                stop_loss=stop_loss
            )

            self.logger.debug(f"Calculated position size: {position_size} for {signal.symbol}")
            return position_size

        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return 0.0

    async def _trigger_signal_callbacks(self, event_type: str, signal: Signal, execution_result: ExecutionResult | None):
        """Trigger signal processing callbacks."""
        for callback in self.signal_callbacks:
            try:
                await callback(event_type, signal, execution_result)
            except Exception as e:
                self.logger.error(f"Error in signal callback: {e}")

    def add_signal_callback(self, callback: Callable):
        """Add a signal processing callback."""
        self.signal_callbacks.append(callback)
        self.logger.info("Added signal callback")

    def get_active_signals(self) -> dict[str, Signal]:
        """Get currently active signals."""
        return self.active_signals.copy()

    def get_signal_summary(self) -> dict[str, Any]:
        """Get summary of signal processing."""
        return {
            "active_signals": len(self.active_signals),
            "max_concurrent_signals": self.max_concurrent_signals,
            "signals": [
                {
                    "symbol": signal.symbol,
                    "side": signal.side,
                    "price": signal.price,
                    "strength": signal.strength,
                    "timestamp": signal.timestamp
                }
                for signal in self.active_signals.values()
            ]
        }


# Factory function for creating signal service
def create_signal_service(execution_engine: ExecutionEngine, risk_manager: RiskManager) -> TradeSignalService:
    """Create a new trade signal service."""
    return TradeSignalService(execution_engine, risk_manager)
