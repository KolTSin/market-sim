import pytest
from environment.environment import Environment
from environment.instrument import Instrument

@pytest.fixture
def env():
    instruments = {"AAPL": Instrument("AAPL", 100.0)}
    return Environment(instruments=instruments)

def test_environment_initialization(env):
    assert isinstance(env.instruments, dict)
    assert "AAPL" in env.instruments
    assert env.time == 0

def test_environment_instruments_have_orderbooks(env):
    inst = env.instruments["AAPL"]
    assert hasattr(inst, "order_book")

    inst.order_book.place_order(price=100, volume=10, side="buy")
    assert len(inst.order_book.bids) == 1

def test_environment_time_progression(env):
    env.time += 1
    assert env.time == 1
