import pytest
import requests
import subprocess
import gevent
from gevent.event import Event
from volttron.platform.vip.agent import Agent
import os
from volttron.platform.keystore import KeyStore

# Creates a helper function for RCP 
#Address to connect to Volttron's VIP socket
VIP_ADDRESS = "ipc:///home/paula-minozzo/.volttron/run/vip.socket"
def rpc_call(peer, method, *args, timeout=20):
    ks = KeyStore("/home/paula-minozzo/.volttron/keystores/test.caller/keystore.json")

    agent = Agent(
        address=VIP_ADDRESS,
        identity="test.caller",
        enable_store=False,
        publickey=ks.public,
        secretkey=ks.secret
    )

    started = Event()
    agent.core.onstart.connect(lambda *a, **kw: started.set())
    gevent.spawn(agent.core.run)

    if not started.wait(timeout=20):
        agent.core.stop()
        raise RuntimeError("Agent failed to start")

    gevent.sleep(2)

    try:
        peers = agent.vip.peerlist().get(timeout=10)
        print("Peers:", peers)
        return agent.vip.rpc.call(peer, method, *args).get(timeout=timeout)
    finally:
        agent.core.stop()
        
def check_volttron_is_scraping():
    result = subprocess.run([
        'ssh', '-i', '/Users/paulaminozzo/.ssh/volttron_vm', '-p', '2222', 'paula-minozzo@localhost',
        'grep "scraping device: home/homeassistant" ~/volttron/volttron.log | tail -1'
    ], capture_output=True, text=True)
    return "scraping device" in result.stdout

STATUS_CODES = {
    200: "Success - request worked perfectly",
    400: "Bad Request - your JSON or parameters are malformed",
    401: "Unauthorized - your token is wrong or missing",
    403: "Forbidden - your token does not have permission",
    404: "Not Found - entity ID does not exist, check for typos",
    500: "Internal Server Error - Home Assistant crashed",
    503: "Service Unavailable - Home Assistant is still starting up"
}

def get_status_message(code):
    return STATUS_CODES.get(code, "Unknown status code")

HA_URL = "http://localhost:8123"
TOKEN = os.environ.get("HA_TOKEN")
HEADERS = {"Authorization": "Bearer " + TOKEN} if TOKEN else None

def require_ha_token():
    if HEADERS is None:
        pytest.skip("HA_TOKEN not set; skipping direct Home Assistant API test")

#Makes a GET request to that URL using requests.get() with our HEADERS
#Checks that the response status code is 200 (meaning success)
def test_get_light_state ():
    response = requests.get(f"{HA_URL}/api/states/input_boolean.test_light", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    print("\n=== TEST: GET light state ===")
    print(f"\nVOLTTRON scraping: {check_volttron_is_scraping()}")
    assert check_volttron_is_scraping(), "VOLTTRON is not scraping Home Assistant!"
    assert "state" in data
    assert data["state"] in ["on", "off"]
    print(f"Response: {response.text}")
    response_message = get_status_message(response.status_code)
    print(f"Status: {response.status_code} - {response_message}")
    print(f"Light state is: {data['state']}")

def test_set_light_on():
    response = requests.post(f"{HA_URL}/api/services/input_boolean/turn_on", headers=HEADERS, json={"entity_id": "input_boolean.test_light"})
    print("\n=== TEST: Set light ON ===")
    print(f"Response: {response.text}")
    response_message = get_status_message(response.status_code)
    print(f"Status: {response.status_code} - {response_message}")
    print(f"\nVOLTTRON scraping: {check_volttron_is_scraping()}")
    assert check_volttron_is_scraping(), "VOLTTRON is not scraping Home Assistant!"
    assert response.status_code == 200

def test_set_light_off():
    response = requests.post(f"{HA_URL}/api/services/input_boolean/turn_off", headers=HEADERS, json={"entity_id": "input_boolean.test_light"})
    print("\n=== TEST: Set light OFF ===")
    print(f"Response: {response.text}")
    response_message = get_status_message(response.status_code)
    print(f"Status: {response.status_code} - {response_message}")
    print(f"\nVOLTTRON scraping: {check_volttron_is_scraping()}")
    assert check_volttron_is_scraping(), "VOLTTRON is not scraping Home Assistant!"
    assert response.status_code == 200

def test_volttron_get_light_state():
    result = rpc_call("platform.driver", "get_point", "home/homeassistant", "test_light")
    print("\n=== TEST: VOLTTRON get light state ===")
    print("Result:", result)
    assert result in [0, 1, "on", "off"]