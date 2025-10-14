# Component Deep Dive
API Connectors: Implements retry logic with exponential backoff and handles API rate limits. Uses a clientOrderId scheme for idempotency.

Execution Engine: Features a finite state machine for order tracking (NEW → ACK → PARTIAL → FILLED / CANCELED). The bracket emulation logic listens for a fill confirmation of an entry order and immediately submits the corresponding Take Profit and Stop Loss orders.

Risk Management: Calculates position sizes based on the ATR-based stop distance. It also checks against global limits (e.g., daily_loss_cap, max_positions) defined in risk.yaml before approving any trade signal.

Strategy Interface: A base class that defines the required methods for any new strategy (e.g., on_bar(bar_data), on_fill(fill_data)). The S1 strategy is the first implementation of this interface.
