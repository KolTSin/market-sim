import pytest
import time
from src.environment.order_book import OrderBook, Order

@pytest.fixture
def book():
    return OrderBook()

def test_add_and_store_orders(book):
    book.place_order(100.0, 5, "buy", agent_id="A1")
    book.place_order(101.0, 5, "sell", agent_id="A2")

    assert len(book.bids) == 1
    assert len(book.asks) == 1
    assert book.bids[0].price == 100.0
    assert book.asks[0].price == 101.0

def test_price_time_priority(book):
    # Two bids, same price, different timestamps
    book.place_order(100.0, 5, "buy", agent_id="A1")
    time.sleep(0.001)  # Ensure different timestamps
    book.place_order(100.0, 5, "buy", agent_id="A2")

    # o1 should be ahead of o2 in time priority
    best = book.best_bid()
    assert best.agent_id == "A1"

def test_basic_matching(book):
    # Matching orders
    book.place_order(101.0, 5, "buy", agent_id="Buyer")
    book.place_order(100.0, 5, "sell", agent_id="Seller")

    trades = book._match_orders()
    assert len(trades) == 1
    trade = trades[0]
    assert trade["buyer"] == "Buyer"
    assert trade["seller"] == "Seller"
    assert trade["volume"] == 5
    assert 100.0 <= trade["price"] <= 101.0

def test_partial_fill(book):
    book.place_order(101.0, 10, "buy", agent_id="Buyer")
    book.place_order(100.0, 4, "sell", agent_id="Seller")
    trades = book._match_orders()
    assert len(trades) == 1
    trade = trades[0]
    assert trade["volume"] == 4

    # Buy order should still be partially on the book
    remaining_buy = next((o for o in book.bids if o.agent_id == "Buyer"), None)
    assert remaining_buy is not None
    assert remaining_buy.quantity == 6

def test_best_bid_ask_and_spread(book):
    book.place_order(99.0, 1, "buy", agent_id="A1")
    book.place_order(100.0, 1, "buy", agent_id="A2")
    book.place_order(101.0, 1, "sell", agent_id="A3")
    book.place_order(102.0, 1, "sell", agent_id="A3")

    best_bid = book.best_bid()
    best_ask = book.best_ask()

    assert best_bid.price == 100.0
    assert best_ask.price == 101.0
    assert (best_ask.price - best_bid.price) == 1.0

def test_str_runs(book):
    book.place_order(100.0, 1, "buy", agent_id="A2")
    book.place_order(101.0, 1, "sell", agent_id="A3")
    s = str(book)
    assert "ORDER BOOK" in s
    assert "Spread" in s
