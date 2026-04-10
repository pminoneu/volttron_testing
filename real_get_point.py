import gevent
from volttron.platform.vip.agent import Agent

class TestAgent(Agent):
    pass

def main():
    agent = TestAgent(identity="test.rpc.agent")
    task = gevent.spawn(agent.core.run)

    gevent.sleep(2)

    try:
        result = agent.vip.rpc.call(
            "platform.driver",
            "get_point",
            "home/homeassistant",
            "test_light"
        ).get(timeout=10)
        print("RPC get_point result:", result)
    finally:
        agent.core.stop()
        task.kill()

if __name__ == "__main__":
    main()