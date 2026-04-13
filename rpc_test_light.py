import gevent
from volttron.platform.vip.agent import Agent
from volttron.platform.agent.known_identities import PLATFORM_DRIVER
from volttron.platform import get_address
import sys


def main():
    if len(sys.argv) != 2:
        print("Usage: python rpc_test_light.py <0|1>")
        sys.exit(1)

    value = int(sys.argv[1])
    if value not in (0, 1):
        print("Value must be 0 or 1")
        sys.exit(1)

    agent = Agent(address=get_address(), identity="demo_setter_agent", enable_store=False)
    g = gevent.spawn(agent.core.run)
    gevent.sleep(2)

    try:
        print(f"Calling set_point(test_light={value})")
        result = agent.vip.rpc.call(
            PLATFORM_DRIVER,
            "set_point",
            "home/homeassistant_light",
            "test_light",
            value,
        ).get(timeout=15)
        print("set_point result:", result)

        gevent.sleep(2)

        verify = agent.vip.rpc.call(
            PLATFORM_DRIVER,
            "get_point",
            "home/homeassistant_light",
            "test_light",
        ).get(timeout=15)
        print("get_point after set_point:", verify)
    except Exception as e:
        print(f"Error during RPC call: {e}")
        import traceback
        traceback.print_exc()
    finally:
        agent.core.stop()
        g.kill()


if __name__ == "__main__":
    main()