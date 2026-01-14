import random
from base_agent import BaseAgent

class RandomAgent(BaseAgent):
    """Example agent that randomly buys/sells."""

    def decide_action(self, state):
        """Randomly decide to buy or sell a random instrument."""

        symbol = random.choice(state["instruments"])
        side = random.choice(["buy", "sell"])
        order_type = random.choice(["market", "limit"])
        volume = random.randint(1, 5)

        price = state["prices"][symbol]
        price *= random.uniform(0.995,1.005)
        price = round(price,2)

        return {
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "price": price,
            "order_type": order_type,
        }
        
        


if __name__ == "__main__":
    agent = RandomAgent(agent_id="RandomTrader", cash=10000.0)
    agent.run(n_steps=20, delay=0.5)
    for sym, qty in agent.portfolio.items():
        print(f"Final holdings of {sym}: {qty} units") 
    print(f"Final cash balance: {agent.cash:.2f}")
    