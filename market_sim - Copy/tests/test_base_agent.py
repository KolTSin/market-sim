import json
from unittest.mock import patch
import pytest

from src.agents.base_agent import BaseAgent


# Patch targets (robust even if you later change the import path)
BASE_AGENT_MOD = BaseAgent.__module__

class FakeSocket:
    """Minimal fake socket: returns queued JSON responses and records sends."""
    def __init__(self, responses):
        self._responses = [json.dumps(r).encode("utf-8") for r in responses]
        self.sent = []
        self.closed = False

    def sendall(self, data: bytes):
        self.sent.append(data)

    def recv(self, n: int) -> bytes:
        assert self._responses, "recv() called but no fake responses left"
        return self._responses.pop(0)

    def close(self):
        self.closed = True


class DummyAgent(BaseAgent):
    """Concrete agent used for testing."""
    def __init__(self, agent_id="A1", decisions=None, **kwargs):
        super().__init__(agent_id=agent_id, **kwargs)
        self._decisions = list(decisions or [])

    def decide_action(self, state: dict):
        return self._decisions.pop(0) if self._decisions else None


def test_connect_and_disconnect():
    fake = FakeSocket(responses=[])
    with patch(f"{BASE_AGENT_MOD}.socket.create_connection", return_value=fake) as cc:
        a = DummyAgent("A1", host="127.0.0.1", port=5555)

        a.connect()
        assert a.connection is fake
        cc.assert_called_once()
        args, kwargs = cc.call_args
        assert args[0] == ("127.0.0.1", 5555)
        assert kwargs["timeout"] == a.socket_timeout

        a.disconnect()
        assert fake.closed is True
        assert a.connection is None

        # idempotent disconnect
        a.disconnect()
        assert a.connection is None


def test_send_message_autoconnects_adds_agent_id_and_parses_response():
    fake = FakeSocket(responses=[{"ok": True, "echo": "pong"}])

    with patch(f"{BASE_AGENT_MOD}.socket.create_connection", return_value=fake):
        a = DummyAgent("A1")
        assert a.connection is None

        msg = {"type": "PING"}
        resp = a.send_message(msg)

        # agent_id injected (BaseAgent mutates message dict)
        assert msg["agent_id"] == "A1"

        sent_obj = json.loads(fake.sent[0].decode("utf-8"))
        assert sent_obj == {"type": "PING", "agent_id": "A1"}

        assert resp == {"ok": True, "echo": "pong"}


def test_get_state_updates_account_snapshot():
    fake = FakeSocket(responses=[
        {"state": {"account": {"cash": 999.0, "portfolio": {"AAA": 2}}}}
    ])

    with patch(f"{BASE_AGENT_MOD}.socket.create_connection", return_value=fake):
        a = DummyAgent("A1", cash=100.0)
        resp = a.get_state()

        assert resp["state"]["account"]["cash"] == 999.0
        assert a.cash == 999.0
        assert a.portfolio == {"AAA": 2}

        sent_obj = json.loads(fake.sent[0].decode("utf-8"))
        assert sent_obj["type"] == "GET_STATE"
        assert sent_obj["agent_id"] == "A1"


def test_place_order_sends_correct_payload():
    fake = FakeSocket(responses=[{"status": "accepted"}])

    with patch(f"{BASE_AGENT_MOD}.socket.create_connection", return_value=fake):
        a = DummyAgent("A1")

        resp = a.place_order(symbol="AAA", side="buy", volume=3, price=10.5, order_type="limit")
        assert resp == {"status": "accepted"}

        sent_obj = json.loads(fake.sent[0].decode("utf-8"))
        assert sent_obj == {
            "type": "PLACE_ORDER",
            "symbol": "AAA",
            "price": 10.5,
            "volume": 3,
            "side": "buy",
            "order_type": "limit",
            "agent_id": "A1",
        }


def test_handle_trade_buyer_and_seller():
    a = DummyAgent("A1", cash=100.0)
    a.portfolio = {"AAA": 1}

    a.handle_trade({"symbol": "AAA", "volume": 2, "price": 10.0, "buyer": "A1", "seller": "B2"})
    assert a.portfolio["AAA"] == 3
    assert a.cash == 80.0

    a.handle_trade({"symbol": "AAA", "volume": 1, "price": 5.0, "buyer": "B2", "seller": "A1"})
    assert a.portfolio["AAA"] == 2
    assert a.cash == 85.0


def test_run_places_order_and_disconnects(monkeypatch):
    fake = FakeSocket(responses=[
        {"state": {"account": {"cash": 1000.0, "portfolio": {}}}},  # get_state
        {"status": "accepted", "order_id": "O-1"},                  # place_order
    ])

    with patch(f"{BASE_AGENT_MOD}.socket.create_connection", return_value=fake):
        monkeypatch.setattr(f"{BASE_AGENT_MOD}.time.sleep", lambda _: None)

        decision = {"symbol": "AAA", "side": "buy", "volume": 1, "price": 10.0, "order_type": "limit"}
        a = DummyAgent("A1", decisions=[decision])

        a.run(n_steps=1, delay=999)

        assert fake.closed is True
        assert a.connection is None
        assert len(fake.sent) == 2

        msg1 = json.loads(fake.sent[0].decode("utf-8"))
        msg2 = json.loads(fake.sent[1].decode("utf-8"))
        assert msg1["type"] == "GET_STATE"
        assert msg2["type"] == "PLACE_ORDER"
