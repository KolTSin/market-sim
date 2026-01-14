import pytest
from environment.instrument import Instrument

@pytest.fixture
def instrument():
    return Instrument(symbol="AAPL", initial_price=100.0)

def test_instrument_initial_state(instrument):
    assert instrument.symbol == "AAPL"
    assert instrument.price == 100.0
    assert hasattr(instrument, "order_book")

def test_price_updates_after_trades(instrument):
    ob = instrument.order_book
    ob.place_order(price=100, volume=5, side="buy")
    ob.place_order(price=99, volume=5, side="sell")

    instrument.update_price()
    assert instrument.price == 99  # last trade price (ask side)

def test_random_walk(instrument):
    old_price = instrument.price
    instrument.random_walk(mu=0.0, sigma=0.1)

    assert instrument.price != old_price
    assert instrument.price > 0
