from volttron.platform.vip.agent import Agent

VIP_ADDRESS = "ipc:///home/paula-minozzo/.volttron/run/vip.socket"

agent = Agent(
    address=VIP_ADDRESS,
    identity="test.caller",
    enable_store=False
)

print("Identity:", agent.core.identity)
print("Public key:", agent.core.publickey)
