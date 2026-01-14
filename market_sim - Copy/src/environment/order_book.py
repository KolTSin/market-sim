import heapq
import time
import uuid
from dataclasses import dataclass, field


# === DATA STRUCTURES =========================================================

@dataclass(order=True)
class Order:
    sort_index: tuple = field(init=False, repr=False)
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    side: str = ""              # 'buy' or 'sell'
    price: float = 0.0
    quantity: int = 0
    order_type: str = "limit"   # 'limit' or 'market'
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self):
        # Used for heap ordering (price-time priority)
        if self.side == "buy":
            # Max-heap: higher price first, earlier timestamp first
            self.sort_index = (-self.price, self.timestamp)
        else:
            # Min-heap: lower price first, earlier timestamp first
            self.sort_index = (self.price, self.timestamp)


@dataclass
class Trade:
    price: float
    volume: int
    symbol: str
    buyer: str
    seller: str
    buyer_order: str
    seller_order: str
    time: int | None = None


# === CORE ORDER BOOK =========================================================

class OrderBook:
    """A clean, testable order book supporting limit and market orders."""

    def __init__(self, symbol: str = None):
        self.symbol = symbol if symbol else "UNKNOWN"
        self.bids: list[Order] = []     # max-heap (by negated price)
        self.asks: list[Order] = []     # min-heap (by price)
        self.trades: list[Trade] = []
        self.current_tick: int | None = None

    # -------------------------------------------------------------------------

    def _add_to_book(self, order: Order):
        """Push the order onto the right heap."""
        heapq.heappush(self.bids if order.side == "buy" else self.asks, order)

    # -------------------------------------------------------------------------

    def _match_against(self, incoming: Order) -> list[Trade]:
        """Match an incoming limit order against the opposite book."""
        trades = []
        opposite = self.asks if incoming.side == "buy" else self.bids
        skipped = []

        while incoming.quantity > 0 and opposite:
            best = opposite[0]

            # Prevent self-trade: if the best order belongs to the same agent,
            # temporarily remove it and continue to the next one.
            if incoming.agent_id and best.agent_id and best.agent_id == incoming.agent_id:
                heapq.heappop(opposite)
                skipped.append(best)
                continue

            # Check if there’s a crossing
            if incoming.side == "buy" and incoming.price < best.price:
                break
            if incoming.side == "sell" and incoming.price > best.price:
                break

            heapq.heappop(opposite)

            traded_vol = min(incoming.quantity, best.quantity)
            trade_price = incoming.price

            trades.append(Trade(
                price=trade_price,
                volume=traded_vol,
                symbol=self.symbol,
                buyer=incoming.agent_id if incoming.side == "buy" else best.agent_id,
                seller=best.agent_id if incoming.side == "buy" else incoming.agent_id,
                buyer_order=incoming.order_id if incoming.side == "buy" else best.order_id,
                seller_order=best.order_id if incoming.side == "buy" else incoming.order_id,
                time=self.current_tick
            ))

            # Adjust quantities
            incoming.quantity -= traded_vol
            best.quantity -= traded_vol

            if best.quantity > 0:
                heapq.heappush(opposite, best)

        # Put skipped self-orders back into the book
        for o in skipped:
            heapq.heappush(opposite, o)

        self.trades.extend(trades)
        return trades

    # -------------------------------------------------------------------------

    @staticmethod
    def _trade_to_dict(trade: Trade) -> dict:
        return {
            "price": trade.price,
            "volume": trade.volume,
            "symbol": trade.symbol,
            "buyer": trade.buyer,
            "seller": trade.seller,
            "buyer_order": trade.buyer_order,
            "seller_order": trade.seller_order,
            "time": trade.time,
        }

    def _match_orders(self) -> list[dict]:
        """Match resting orders and return serialized trades."""
        while self.bids and self.asks:
            best_bid = self.bids[0]
            best_ask = self.asks[0]
            if best_bid.price < best_ask.price:
                break

            bid = heapq.heappop(self.bids)
            ask = heapq.heappop(self.asks)

            traded_vol = min(bid.quantity, ask.quantity)
            trade_price = ask.price

            trade = Trade(
                price=trade_price,
                volume=traded_vol,
                symbol=self.symbol,
                buyer=bid.agent_id,
                seller=ask.agent_id,
                buyer_order=bid.order_id,
                seller_order=ask.order_id,
                time=self.current_tick,
            )

            self.trades.append(trade)

            bid.quantity -= traded_vol
            ask.quantity -= traded_vol

            if bid.quantity > 0:
                heapq.heappush(self.bids, bid)
            if ask.quantity > 0:
                heapq.heappush(self.asks, ask)

        matched_trades = self.trades
        self.trades = []
        return [self._trade_to_dict(trade) for trade in matched_trades]

    def _execute_market_order(self, order: Order) -> dict:
        """Execute a market order against the opposite book (no book entry)."""
        trades = []
        total_filled = 0
        total_cost = 0.0
        opposite = self.asks if order.side == "buy" else self.bids

        while order.quantity > 0 and opposite:
            best = heapq.heappop(opposite)
            traded_vol = min(order.quantity, best.quantity)
            trade_price = best.price

            trades.append(Trade(
                price=trade_price,
                volume=traded_vol,
                symbol=self.symbol,
                buyer=order.agent_id if order.side == "buy" else best.agent_id,
                seller=best.agent_id if order.side == "buy" else order.agent_id,
                buyer_order=order.order_id if order.side == "buy" else best.order_id,
                seller_order=best.order_id if order.side == "buy" else order.order_id,
                time=self.current_tick
            ))

            total_filled += traded_vol
            total_cost += traded_vol * trade_price

            order.quantity -= traded_vol
            best.quantity -= traded_vol
            if best.quantity > 0:
                heapq.heappush(opposite, best)

        self.trades.extend(trades)

        avg_price = total_cost / total_filled if total_filled else None
        return {
            "trades": trades,
            "filled": total_filled,
            "unfilled": order.quantity,
            "avg_price": avg_price,
        }

    # -------------------------------------------------------------------------

    def place_order(self, price: float, volume: int, side: str, order_type: str = "limit", agent_id: str = "") -> list[Trade]:
        """Place a new order into the book."""
        order = Order(
            agent_id=agent_id,
            side=side,
            price=price,
            quantity=volume,
            order_type=order_type,
        )
        if order_type == "limit":
            return self._place_limit_order(order)
        elif order_type == "market":
            result = self._place_market_order(order)
            return result["trades"]
        else:
            raise ValueError(f"Unknown order type: {order_type}")

    def _place_limit_order(self, order: Order) -> list[Trade]:
        """Add a limit order, possibly matching immediately."""
        trades = self._match_against(order)
        if order.quantity > 0:
            self._add_to_book(order)
        return trades

    def _place_market_order(self, order: Order) -> dict:
        """Execute immediately against the opposite book."""
        return self._execute_market_order(order)

    # -------------------------------------------------------------------------

    def best_bid(self):
        return max(self.bids, key=lambda o: o.price, default=None)

    def best_ask(self):
        return min(self.asks, key=lambda o: o.price, default=None)

    # -------------------------------------------------------------------------

    def fmt_orders(self, orders, side: str) -> str:
        if not orders:
            return "  (empty)"
        sorted_orders = sorted(
            orders,
            key=lambda o: (-o.price if side == "BID" else o.price, o.timestamp)
        )
        return "\n".join(
            f"  {side:<5} | {o.price:>8.2f} | {o.quantity:>5d} | {o.agent_id}"
            for o in sorted_orders
        )

    def __str__(self) -> str:
        header = f"\n=== ORDER BOOK ({self.symbol}) ==="
        bids_str = self.fmt_orders(self.bids, "BID")
        asks_str = self.fmt_orders(self.asks, "ASK")
        spread = None
        if self.bids and self.asks:
            spread = self.best_ask().price - self.best_bid().price
        spread_str = f"\nSpread: {spread:.2f}" if spread is not None else "\nSpread: N/A"
        return f"{header}\n{bids_str}\n---\n{asks_str}{spread_str}\n"
