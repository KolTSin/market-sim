# Dynamic Programming Agent

from base_agent import BaseAgent

class DPAgent(BaseAgent):
    def __init__(self, agent_id, host="127.0.0.1", port=5555, cash=100):
        super().__init__(agent_id, host, port, cash)

    def decide_action(self, state):
        return super().decide_action(state)