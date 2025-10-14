"""
Trade Entry Service.

This module provides the main service for trade entry functionality,
integrating trend detection, signal generation, risk management,
and order execution.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from grodtd.connectors.robinhood import RobinhoodConnector
from grodtd.execution.engine import ExecutionEngine
from grodtd.execution.signal_service import TradeSignalService
from grodtd.execution.trade_exit_service import TradeExitService, create_trade_exit_service
from grodtd.execution.strategy_gating_service import StrategyGatingService, create_strategy_gating_service
from grodtd.risk.manager import RiskLimits, RiskManager
from grodtd.storage.interfaces import OHLCVBar
from grodtd.strategies.base import Signal, StrategyState, StrategyManager
from grodtd.strategies.s1_trend_strategy import S1TrendStrategy


@dataclass
class TradeEntryResult:
    """Result of trade entry processing."""
    success: bool
    signals_generated: int
    orders_placed: int
    errors: list[str]
    processing_time: float


class TradeEntryService:
    """
    Main service for trade entry functionality.
    
    This service coordinates the entire trade entry process:
    1. Trend detection and signal generation
    2. Signal validation and processing
    3. Risk management and position sizing
    4. Order creation and execution
    """

    def __init__(
        self,
        connector: RobinhoodConnector,
        risk_manager: RiskManager,
        symbol: str,
        config: dict[str, Any]
    ):
        self.connector = connector
        self.risk_manager = risk_manager
        self.symbol = symbol
        self.config = config

        # Initialize components
        self.execution_engine = ExecutionEngine(connector, risk_manager)
        self.signal_service = TradeSignalService(self.execution_engine, risk_manager)
        
        # Initialize strategy gating service
        gating_config_path = config.get('gating', {}).get('config_path')
        self.gating_service = create_strategy_gating_service(gating_config_path)
        
        # Initialize strategy manager with gating service
        self.strategy_manager = StrategyManager(self.gating_service)
        
        # Add S1 strategy to manager
        self.strategy = S1TrendStrategy(symbol, config.get('strategy', {}))
        self.strategy_manager.add_strategy(self.strategy)
        
        # Initialize trade exit service
        exit_config = config.get('trade_exit', {})
        self.exit_service = create_trade_exit_service(self.execution_engine, risk_manager, exit_config)

        # Service state
        self.is_running = False
        self.last_processing_time: datetime | None = None
        self.processing_callbacks: list[Callable] = []

        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized TradeEntryService for {symbol}")

    async def start(self):
        """Start the trade entry service."""
        if self.is_running:
            self.logger.warning("Trade entry service is already running")
            return

        self.is_running = True
        self.logger.info("Started trade entry service")

        # Add execution callbacks
        self.execution_engine.add_execution_callback(self._on_order_fill)
        self.signal_service.add_signal_callback(self._on_signal_processed)

    async def stop(self):
        """Stop the trade entry service."""
        if not self.is_running:
            self.logger.warning("Trade entry service is not running")
            return

        self.is_running = False
        self.logger.info("Stopped trade entry service")

    async def process_market_data(self, market_data: OHLCVBar) -> TradeEntryResult:
        """
        Process market data and generate trade entries.
        
        Args:
            market_data: Latest market data bar
            
        Returns:
            TradeEntryResult with processing details
        """
        start_time = datetime.now()
        errors = []
        signals_generated = 0
        orders_placed = 0

        try:
            if not self.is_running:
                errors.append("Service is not running")
                return TradeEntryResult(False, 0, 0, errors, 0.0)

            # Create strategy state
            state = StrategyState(
                symbol=self.symbol,
                current_price=market_data.close,
                market_data=None,  # Single bar, not DataFrame
                timestamp=market_data.timestamp
            )

            # Run strategies with gating applied
            signals = await self.strategy_manager.run_strategies(state)
            signals_generated = len(signals)

            if signals:
                self.logger.info(f"Generated {signals_generated} signals for {self.symbol}")

                # Process signals
                processing_results = await self.signal_service.process_multiple_signals(signals)

                # Count successful orders
                orders_placed = sum(1 for result in processing_results if result.success)

                # Collect errors
                for result in processing_results:
                    if not result.success and result.error_message:
                        errors.append(f"Signal processing error: {result.error_message}")

            # Update last processing time
            self.last_processing_time = datetime.now()

            # Trigger callbacks
            await self._trigger_processing_callbacks("market_data_processed", {
                "symbol": self.symbol,
                "price": market_data.close,
                "signals_generated": signals_generated,
                "orders_placed": orders_placed,
                "errors": errors
            })

        except Exception as e:
            error_msg = f"Error processing market data: {e}"
            self.logger.error(error_msg)
            errors.append(error_msg)

        processing_time = (datetime.now() - start_time).total_seconds()

        return TradeEntryResult(
            success=len(errors) == 0,
            signals_generated=signals_generated,
            orders_placed=orders_placed,
            errors=errors,
            processing_time=processing_time
        )

    async def get_service_status(self) -> dict[str, Any]:
        """Get current service status."""
        strategy_state = self.strategy.get_strategy_state()
        signal_summary = self.signal_service.get_signal_summary()
        execution_summary = self.execution_engine.get_execution_summary()
        risk_summary = self.risk_manager.get_risk_summary()
        gating_summary = self.gating_service.get_gating_summary(self.symbol)

        return {
            "service_running": self.is_running,
            "symbol": self.symbol,
            "last_processing_time": self.last_processing_time,
            "strategy": strategy_state,
            "signals": signal_summary,
            "execution": execution_summary,
            "risk": risk_summary,
            "gating": gating_summary
        }

    async def cancel_all_signals(self) -> int:
        """Cancel all active signals."""
        active_signals = self.signal_service.get_active_signals()
        cancelled_count = 0

        for symbol in list(active_signals.keys()):
            if await self.signal_service.cancel_signal(symbol):
                cancelled_count += 1

        self.logger.info(f"Cancelled {cancelled_count} active signals")
        return cancelled_count

    async def _on_order_fill(self, event_type: str, order):
        """Handle order fill events."""
        self.logger.info(f"Order fill event: {event_type} for {order.symbol}")

        # Notify strategy of fill
        if hasattr(order, 'symbol') and order.symbol == self.symbol:
            # Create signal from order for strategy notification
            signal = Signal(
                symbol=order.symbol,
                side=order.side,
                strength=1.0,
                price=order.average_fill_price or order.price,
                timestamp=datetime.now()
            )

            fill_data = {
                "order_id": order.id,
                "quantity": order.filled_quantity,
                "price": order.average_fill_price or order.price,
                "timestamp": order.filled_at or datetime.now()
            }

            await self.strategy.on_fill(signal, fill_data)
            
            # Auto-create bracket orders if enabled
            if self.config.get('trade_exit', {}).get('auto_exit_on_fill', True):
                await self._create_bracket_orders(order)

    async def _on_signal_processed(self, event_type: str, signal: Signal, execution_result):
        """Handle signal processing events."""
        self.logger.debug(f"Signal processed: {event_type} for {signal.symbol}")

    async def _trigger_processing_callbacks(self, event_type: str, data: dict[str, Any]):
        """Trigger processing callbacks."""
        for callback in self.processing_callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                self.logger.error(f"Error in processing callback: {e}")

    def add_processing_callback(self, callback: Callable):
        """Add a processing callback."""
        self.processing_callbacks.append(callback)
        self.logger.info("Added processing callback")

    async def _create_bracket_orders(self, entry_order):
        """Create bracket orders for a filled entry order."""
        try:
            # Get ATR from risk manager (if available)
            atr = self._get_atr_for_symbol(entry_order.symbol)
            if not atr:
                self.logger.warning(f"No ATR available for {entry_order.symbol}, skipping bracket orders")
                return
            
            # Create bracket order
            result = await self.exit_service.create_bracket_order(
                entry_order=entry_order,
                entry_price=entry_order.average_fill_price or entry_order.price,
                atr=atr,
                risk_reward_ratio=self.config.get('trade_exit', {}).get('risk_reward_ratio', 1.5)
            )
            
            if result.success:
                self.logger.info(f"Created bracket order: {result.bracket_order_id}")
            else:
                self.logger.error(f"Failed to create bracket order: {result.error_message}")
                
        except Exception as e:
            self.logger.error(f"Error creating bracket orders: {e}")

    def _get_atr_for_symbol(self, symbol: str) -> float:
        """Get ATR for a symbol from risk manager or strategy."""
        # This is a simplified implementation - in practice, you'd get ATR from
        # the strategy's technical indicators or market data
        # For now, return a default ATR based on typical crypto volatility
        return 0.02  # 2% ATR as default


# Factory function for creating trade entry service
def create_trade_entry_service(
    connector: RobinhoodConnector,
    risk_limits: RiskLimits,
    account_balance: float,
    symbol: str,
    config: dict[str, Any]
) -> TradeEntryService:
    """Create a new trade entry service."""
    risk_manager = RiskManager(risk_limits, account_balance)
    return TradeEntryService(connector, risk_manager, symbol, config)
