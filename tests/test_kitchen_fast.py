import sys
import os

# Ensure src is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crew_agents import LifeOSAgents


def test_kitchen_is_fast():
    """Verifies that the Kitchen agent is configured to use the fast execution path."""
    agents = LifeOSAgents()
    kitchen_cfg = agents.config.get('kitchen', {})

    assert kitchen_cfg, "Kitchen config should exist in agents.yaml"
    assert kitchen_cfg.get('execution_mode') == 'fast', "Kitchen should be configured with execution_mode: 'fast'"


if __name__ == '__main__':
    # Simple runner for local verification
    test_kitchen_is_fast()
    print("✅ Kitchen is configured as fast.")