import socket
import threading
import json
import time
from src.environment.environment import Environment
from src.environment.instrument import Instrument

class MarketServer:
    def __init__(self,env: Environment|None = None, host: str="127.0.0.1", port: int=5555, tick_interval: float=1.0):
        
        self.env: Environment = Environment({
            "AAPL": Instrument("AAPL", 100.0),
            "GOOG": Instrument("GOOG", 150.0),
        }) if env is None else env
        self.host: str = host
        self.port: int = port
        self.agents: dict[str, tuple[str, int]] = {}
        self.tick_interval: float = tick_interval
        self.running: bool = False
        self.pending_orders: list[dict] = []

    def tick_loop(self):
        """Advance the environment continuously."""
        while self.running:
            result = self.env.tick()
            if result["trades"]:
                for trade in result["trades"]:
                    print(f"[TRADE] {trade}")
            prices = {s: inst.price for s, inst in self.env.instruments.items()}
            print(f"[TICK {self.env.time}] Prices: {prices}")
            time.sleep(self.tick_interval)

    def start(self):
        self.running = True

        # Start ticking in the background
        tick_thread = threading.Thread(target=self.tick_loop, daemon=True)
        tick_thread.start()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            print(f"MarketServer running on {self.host}:{self.port}")
            while self.running:
                conn, addr = s.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr)).start()

    def handle_client(self, conn, addr):
        print(f"Agent connected: {addr}")
        self.env.add_account(addr)
        agent_id = None
        with conn:
            while self.running:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    msg = json.loads(data.decode())
                    agent_id = msg["agent_id"]
                    if agent_id not in self.env.agent_accounts:
                        self.env.add_account(agent_id)
                        print(f"[SERVER] Registered new agent: {agent_id}")
                    response = self.process_message(msg, addr)
                    print(response)
                    conn.sendall(json.dumps(response).encode())
                except Exception as e:
                    print(f"[SERVER] Error handling {agent_id or addr}: {e}")
                    break

    def process_message(self, msg: dict, agent_id=None):
        mtype = msg.get("type")

        if mtype == "PLACE_ORDER":
            order = {
                "symbol": msg["symbol"],
                "price": msg["price"],
                "volume": msg["volume"],
                "side": msg["side"],
                "order_type": msg.get("order_type", "limit"),
                "agent_id": msg.get("agent_id", str(agent_id)),
            }
            self.env.submit_order(order)
            return {"type": "ACK", "status": "queued"}

        elif mtype == "GET_BOOK":
            sym = msg["symbol"]
            ob = self.env.instruments[sym].order_book
            return {"type": "BOOK", "bids": list(ob.bids), "asks": list(ob.asks)}

        elif mtype == "GET_STATE":
            return {"type": "STATE", "state": self.env.get_state(agent_id)}

        elif mtype == "GET_TIME":
            return {"type": "TIME", "time": self.env.time}

        else:
            return {"error": f"Unknown message type: {mtype}"}
        
    def settle_trade(self, trade):
        cost = trade.price * trade.volume
        buyer = self.agents.get(trade.buyer)
        seller = self.agents.get(trade.seller)

        if buyer:
            buyer["cash"] -= cost
            buyer["portfolio"][trade.symbol] = buyer["portfolio"].get(trade.symbol, 0) + trade.volume

        if seller:
            seller["cash"] += cost
            seller["portfolio"][trade.symbol] = seller["portfolio"].get(trade.symbol, 0) - trade.volume

        print(f"[SETTLE] {trade.symbol} {trade.volume}@{trade.price:.2f} "
            f"Buyer={trade.buyer} Seller={trade.seller}")
        
    def notify_participants(self, trade):
        for role, agent_id in [("buyer", trade.buyer), ("seller", trade.seller)]:
            agent = self.agents.get(agent_id)
            if not agent:
                continue
            msg = {"type": "TRADE_EXECUTED", "trade": trade.__dict__}
            try:
                agent["conn"].sendall(json.dumps(msg).encode())
            except Exception as e:
                print(f"[WARN] Could not notify {agent_id}: {e}")




