import gevent
import os
import sys
import traceback
from volttron.platform import get_address
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from volttron.platform.vip.agent import Agent

DEFAULT_VOLTTRON_HOME = "/home/paula-minozzo/.volttron_homeassistant_demo"


def main():
    os.environ.setdefault("VOLTTRON_HOME", DEFAULT_VOLTTRON_HOME)

    if len(sys.argv) != 2:
        print("Usage: python rpc_test_lock.py <0|1>")
        sys.exit(1)

    value = int(sys.argv[1])
    if value not in (0, 1):
        print("Value must be 0 or 1")
        sys.exit(1)

    agent = Agent(
        address=get_address(),
        identity="demo_setter_agent",
        enable_store=False,
    )
    task = gevent.spawn(agent.core.run)
    gevent.sleep(2)

    try:
        print(f"Calling set_point(test_lock={value})")
        result = agent.vip.rpc.call(
            PLATFORM_DRIVER,
            "set_point",
            "home/homeassistant_light",
            "test_lock",
            value,
        ).get(timeout=15)
        print("set_point result:", result)

        gevent.sleep(2)

        verify = agent.vip.rpc.call(
            PLATFORM_DRIVER,
            "get_point",
            "home/homeassistant_light",
            "test_lock",
        ).get(timeout=15)
        print("get_point after set_point:", verify)
    except Exception as exc:
        print(f"Error during RPC call: {exc}")
        traceback.print_exc()
    finally:
        agent.core.stop()
        task.kill()


if __name__ == "__main__":
    main()
