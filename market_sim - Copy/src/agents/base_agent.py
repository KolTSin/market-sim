import json
import socket
import time
from abc import ABC, abstractmethod


class BaseAgent(ABC):
    """Base class for all trading agents."""

    def __init__(self, agent_id, host="127.0.0.1", port=5555, cash=100_000.0):
        self.agent_id = agent_id
        self.host = host
        self.port = port
        self.cash = cash
        self.portfolio = {}  # symbol -> quantity
        self.socket_timeout = 2.0
        self.connection = None

    # ------------------------------------------------------------------
    # CONNECTION MANAGEMENT
    # ------------------------------------------------------------------

    def connect(self):
        self.connection = socket.create_connection((self.host, self.port), timeout=self.socket_timeout)
        print(f"[{self.agent_id}] Connected to market @ {self.host}:{self.port}")


    def disconnect(self):
        """Close the socket cleanly."""
        if self.connection:
            self.connection.close()
            self.connection = None
            print(f"[{self.agent_id}] Disconnected.")

    # ------------------------------------------------------------------
    # COMMUNICATION
    # ------------------------------------------------------------------

    def send_message(self, msg: dict) -> dict:
        """Send one JSON message and receive one response."""
        if not self.connection:
            self.connect()

        msg["agent_id"] = self.agent_id
        self.connection.sendall(json.dumps(msg).encode())
        data = self.connection.recv(8192)
        response = json.loads(data.decode())
        print(f"[{self.agent_id}] Sent: {msg} | Received: {response}")
        return response


    def get_state(self) -> dict:
        """Request current market state from the server."""
        response = self.send_message({"type": "GET_STATE"})
        state = response.get("state", {})
        account = state.get("account", {})
        d_cash = self.update_account(account)
        if d_cash != 0:
            print(f"[{self.agent_id}] Cash changed by {d_cash:,.2f}. ")
        return response

    def place_order(self, symbol, side, volume, price=0.0, order_type="limit"):
        """Send an order to the market."""
        msg = {
            "type": "PLACE_ORDER",
            "symbol": symbol,
            "price": price,
            "volume": volume,
            "side": side,
            "order_type": order_type,
        }
        resp = self.send_message(msg)
        return resp

    # ------------------------------------------------------------------
    # ACCOUNTING HELPERS
    # ------------------------------------------------------------------

    def update_account(self, account: dict) -> float:
        """
        Update the local account snapshot (cash & portfolio) from a dict:

            {"cash": <float>, "portfolio": {symbol: qty, ...}}

        Returns the change in cash since the last snapshot.
        """
        if not account:
            return 0.0

        new_cash = account.get("cash", self.cash)
        new_portfolio = account.get("portfolio", self.portfolio)

        delta_cash = new_cash - self.cash
        self.cash = new_cash
        self.portfolio = new_portfolio
        return delta_cash


    def update_portfolio(self, symbol, delta_qty, delta_cash):
        """Adjust holdings after trade settlement."""
        self.portfolio[symbol] = self.portfolio.get(symbol, 0) + delta_qty
        self.cash += delta_cash

    def handle_trade(self, trade):
        sym, qty, price = trade["symbol"], trade["volume"], trade["price"]
        if trade["buyer"] == self.agent_id:
            self.update_portfolio(sym, +qty, -price * qty)
        elif trade["seller"] == self.agent_id:
            self.update_portfolio(sym, -qty, +price * qty)
        print(f"[{self.agent_id}] Updated after trade: {trade}")

    # ------------------------------------------------------------------
    # FORMATTING
    # ------------------------------------------------------------------

    def print_portfolio(self):
        """Pretty-print the agent's current cash and portfolio holdings."""
        print(f"\n[{self.agent_id}] Portfolio Summary")
        print("─" * 40)

        # Cash
        print(f"Cash: {self.cash:,.2f}")

        # Portfolio
        if not self.portfolio:
            print("Portfolio: (empty)")
            print("─" * 40)
            return
        
        print("Holdings:")
        for symbol, qty in self.portfolio.items():
            print(f"  {symbol:<8} |  Qty: {qty:>6}")

        print("─" * 40)


    # ------------------------------------------------------------------
    # BEHAVIOR INTERFACE
    # ------------------------------------------------------------------

    @abstractmethod
    def decide_action(self, state: dict):
        """
        Called each tick.
        Must return either:
        - None (do nothing)
        - A dict with order params:
          {"symbol": ..., "side": ..., "volume": ..., "price": ..., "order_type": ...}
        """
        pass

    # ------------------------------------------------------------------
    # MAIN LOOP
    # ------------------------------------------------------------------

    def run(self, n_steps=10, delay=1.0):
        """Main loop: query market, decide, place order."""
        self.connect()
        try:
            for step in range(n_steps):
                state_resp = self.get_state()
                state = state_resp.get("state", {})

                # cash / portfolio already updated in send_message via update_account
                print(f"[{self.agent_id}] Step {step} - Market State: {state}")
                self.print_portfolio()

                decision = self.decide_action(state)
                print(f"decision at step {step}: {decision}")
                if decision:
                    resp = self.place_order(**decision)
                    print(f"[{self.agent_id}] Sent order: {decision} -> {resp}")

                time.sleep(delay)

        finally:
            self.disconnect()
