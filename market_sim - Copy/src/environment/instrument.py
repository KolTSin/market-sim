from .order_book import OrderBook

class Instrument:
    """A financial instrument traded in the market."""
    def __init__(self, symbol: str, initial_price: float = 100.0):
        self.symbol: str = symbol
        self.price: float = initial_price  # Default initial price
        self.order_book: OrderBook = OrderBook(symbol)

    def update_price(self):
        """Update the price of the instrument based on the trades in the orderbook."""
        trades = self.order_book.trades
        print(f"trades in order book: {self.order_book.trades}")
        print(trades)
        if trades:
            # Simple price update: last trade price
            print(f"Updating price for {self.symbol} based on trades: {trades}")
            self.price = trades[-1].price
    
    def random_walk(self, mu: float = 0.0, sigma: float = 1.0):
        """Update the price using a simple random walk model."""
        import random
        delta = random.gauss(mu, sigma)
        self.price += delta
        if self.price < 0:
            self.price = 0.01  # Prevent negative prices