import socket
import json
import threading
import time
import pytest

from src.environment.environment import Environment
from src.environment.instrument import Instrument
from src.server.market_server import MarketServer

HOST = "127.0.0.1"
PORT = 6000

@pytest.fixture(scope="module")
def running_server():
    """Spin up a MarketServer in a background thread for testing."""
    instruments = {
        "AAPL": Instrument("AAPL", 100.0),
        "GOOG": Instrument("GOOG", 150.0),
    }
    env = Environment(instruments)
    server = MarketServer(env=env, host=HOST, port=PORT, tick_interval=0.2)

    t = threading.Thread(target=server.start, daemon=True)
    t.start()

    # Wait until server is running
    time.sleep(0.5)
    yield server

    server.running = False
    time.sleep(0.2)

def send_recv(msg: dict):
    """Utility to send one message and receive one response."""
    with socket.create_connection((HOST, PORT), timeout=2) as s:
        s.sendall(json.dumps(msg).encode())
        data = s.recv(4096)
    return json.loads(data.decode())

def test_place_order_and_tick(running_server):
    # Place a buy limit order
    resp1 = send_recv({
        "type": "PLACE_ORDER",
        "symbol": "AAPL",
        "price": 99.5,
        "volume": 3,
        "side": "buy",
        "order_type": "limit",
        "agent_id": "Agent1"
    })
    assert resp1["status"] == "queued"

    # Place a matching sell order
    resp2 = send_recv({
        "type": "PLACE_ORDER",
        "symbol": "AAPL",
        "price": 99.0,
        "volume": 3,
        "side": "sell",
        "order_type": "limit",
        "agent_id": "Agent2"
    })
    assert resp2["status"] == "queued"

    # Allow one tick to process the orders
    time.sleep(2)

    # Query environment state
    resp3 = send_recv({"type": "GET_STATE"})
    state = resp3["state"]
    assert "AAPL" in state["prices"]
    # Expect trade_log not empty
    assert len(running_server.env.trade_log) >= 1

def test_market_order_execution(running_server):
    # Add some liquidity
    send_recv({
        "type": "PLACE_ORDER",
        "symbol": "GOOG",
        "price": 150.5,
        "volume": 2,
        "side": "sell",
        "order_type": "limit",
        "agent_id": "Maker"
    })

    # Immediately cross with a market buy
    send_recv({
        "type": "PLACE_ORDER",
        "symbol": "GOOG",
        "price": 0,
        "volume": 1,
        "side": "buy",
        "order_type": "market",
        "agent_id": "Taker"
    })

    time.sleep(0.3)
    trades = [t for t in running_server.env.trade_log if t["symbol"] == "GOOG"]
    assert trades, "No trades executed for market order"
    last_trade = trades[-1]
    assert last_trade["buyer"] == "Taker"
    assert last_trade["seller"] == "Maker"
    assert last_trade["price"] == pytest.approx(150.5)
