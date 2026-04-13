import os
import traceback

import gevent
from volttron.platform import get_address
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from volttron.platform.vip.agent import Agent

DEFAULT_VOLTTRON_HOME = "/home/paula-minozzo/.volttron_homeassistant_demo"


class TestAgent(Agent):
    pass


def main():
    os.environ.setdefault("VOLTTRON_HOME", DEFAULT_VOLTTRON_HOME)

    agent = TestAgent(
        address=get_address(),
        identity="demo_setter_agent",
        enable_store=False,
    )
    task = gevent.spawn(agent.core.run)

    gevent.sleep(2)

    try:
        result = agent.vip.rpc.call(
            PLATFORM_DRIVER,
            "get_point",
            "home/homeassistant_light",
            "test_lock",
        ).get(timeout=10)
        print("RPC get_point result:", result)
    except Exception as exc:
        print(f"Error during RPC call: {exc}")
        traceback.print_exc()
    finally:
        agent.core.stop()
        task.kill()


if __name__ == "__main__":
    main()
