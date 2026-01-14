import typing
import time
from .instrument import Instrument

class Environment:
    """A simulated market environment for trading agents."""
    def __init__(self, instruments: dict[str, Instrument]):
        self.instruments: dict[str, Instrument] = instruments
        self.time: int = 0
        self.trade_log: list[dict] = []  # Store history of trades
        self.pending_orders: list[dict] = [] # Orders to be processed each tick
        self.agent_accounts: dict = {}

    def add_account(self, agent_id):
        """Create a new account for an agent (identified by addr / agent_id)."""
        self.agent_accounts[agent_id] = {
            "cash": 1_000_000.0,
            "portfolio": {},
        }

    def submit_order(self, order: dict):
        """Submit a new order to the environment."""
        self.pending_orders.append(order)

    def update_accounts(self, trade):
        """
        Apply a single Trade to buyer and seller accounts.

        Trade has: price, volume, symbol, buyer, seller.
        """
        buyer = trade.buyer
        seller = trade.seller
        symbol = trade.symbol
        volume = trade.volume
        value = trade.price * volume

        # Make sure both accounts exist
        if buyer not in self.agent_accounts:
            self.add_account(buyer)
        if seller not in self.agent_accounts:
            self.add_account(seller)

        buyer_acc = self.agent_accounts[buyer]
        seller_acc = self.agent_accounts[seller]

        # Buyer: loses cash, gains shares
        buyer_acc["cash"] -= value
        buyer_pos = buyer_acc["portfolio"].get(symbol, 0)
        buyer_acc["portfolio"][symbol] = buyer_pos + volume

        # Seller: gains cash, loses shares
        seller_acc["cash"] += value
        seller_pos = seller_acc["portfolio"].get(symbol, 0)
        seller_acc["portfolio"][symbol] = seller_pos - volume

        

    def process_orders(self):
        """Execute all pending orders for this tick."""
        all_trades = []
        for order in self.pending_orders:
            symbol = order["symbol"]
            inst = self.instruments[symbol]
            trades = inst.order_book.place_order(
                price=order["price"],
                volume=order["volume"],
                side=order["side"],
                order_type=order.get("order_type", "limit"),
                agent_id=order.get("agent_id", "unknown"),
            )
            for t in trades:
                t.time = self.time
                all_trades.append(t)
                # NEW: update accounts based on this trade
                self.update_accounts(t)

        self.pending_orders.clear()
        if all_trades:
            self.trade_log.extend(all_trades)
        return all_trades

    
    def reset(self):
        self.time = 0
        self.trade_log.clear()
        for instrument in self.instruments.values():
            instrument.order_book.bids.clear()
            instrument.order_book.asks.clear()
            instrument.order_book.trades.clear()
        return self.get_state()


    def tick(self):
        """Advance one simulation step."""
        self.time += 1
        trades = self.process_orders()
        self.update_prices()
        return {"time": self.time, "trades": trades, "state": self.get_state()}

    def run_continuous(self, interval=1.0):
        """
        Run ticks continuously in a blocking loop (for testing).
        Each tick happens every `interval` seconds.
        """
        print("Environment continuous loop started.")
        while True:
            state = self.tick()
            print(f"[Tick {self.time}] Prices:", {s: d['price'] for s, d in state['instruments'].items()})
            time.sleep(interval)

    def get_state(self, addr = None):
        """Return a snapshot of current prices and order book depths."""
        print(addr)
        if addr:
            return {
                "time": self.time,
                "instruments": [sym for sym in self.instruments.keys()],
                "order_books": {
                    sym: {
                        "bids": len(inst.order_book.bids),
                        "asks": len(inst.order_book.asks)
                    }
                    for sym, inst in self.instruments.items()
                },
                "prices": {sym: inst.price for sym, inst in self.instruments.items()},
                "account": self.agent_accounts[addr]
            }
        else:
            return {
                "time": self.time,
                "instruments": [sym for sym in self.instruments.keys()],
                "order_books": {
                    sym: {
                        "bids": len(inst.order_book.bids),
                        "asks": len(inst.order_book.asks)
                    }
                    for sym, inst in self.instruments.items()
                },
                "prices": {sym: inst.price for sym, inst in self.instruments.items()},
            }
        
    
    def update_prices(self):
        """Update instrument prices based on last trades."""
        for sym, inst in self.instruments.items():
            trades = [t for t in self.trade_log if t.symbol == sym and t.time == self.time]
            if trades:
                # Update price to last trade price
                inst.price = trades[-1].price