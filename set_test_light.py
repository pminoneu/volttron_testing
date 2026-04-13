import gevent
import os
import sys
from volttron.platform import get_address
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from volttron.platform.vip.agent import Agent

DEFAULT_VOLTTRON_HOME = "/home/paula-minozzo/.volttron_homeassistant_demo"


def main():
    os.environ.setdefault("VOLTTRON_HOME", DEFAULT_VOLTTRON_HOME)

    if len(sys.argv) != 2:
        print("Usage: python set_test_light.py <0|1>")
        sys.exit(1)

    try:
        value = int(sys.argv[1])
    except ValueError:
        print("Value must be 0 or 1")
        sys.exit(1)

    if value not in (0, 1):
        print("Value must be 0 or 1")
        sys.exit(1)

    agent = Agent(
        address=get_address(),
        identity="demo_setter_agent",
        enable_store=False,
    )
    task = gevent.spawn(agent.core.run)
    gevent.sleep(1)

    try:
        result = agent.vip.rpc.call(
            PLATFORM_DRIVER,
            "set_point",
            "home/homeassistant_light",
            "test_light",
            value,
        ).get(timeout=10)

        print(f"set_point succeeded: value={value}, result={result}")
    finally:
        agent.core.stop()
        task.kill()


if __name__ == "__main__":
    main()
