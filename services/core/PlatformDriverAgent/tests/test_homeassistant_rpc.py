"""
Home Assistant integration test for the VOLTTRON PlatformDriverAgent.

Requirements:
- A working VOLTTRON checkout with project dependencies installed.
- A reachable Home Assistant instance.
- A valid Home Assistant long-lived access token.
- A writable Home Assistant entity such as `input_boolean.test_light`.

Required environment variables:
- HA_TOKEN: Home Assistant long-lived access token.
- HA_IP: Hostname or IP for Home Assistant. Example: localhost
- HA_PORT: Home Assistant port. Example: 8123
- HA_ENTITY_ID: Writable entity to test. Example: input_boolean.test_light

Example on how to run this test:
HA_TOKEN="your_home_assistant_token" \
HA_IP="localhost" \
HA_PORT="8123" \
HA_ENTITY_ID="input_boolean.test_light" \
env/bin/python -m pytest services/core/PlatformDriverAgent/tests/test_homeassistant_rpc.py -s -v

What this test does:
- Verifies Home Assistant authorization with a direct API call.
- Configures the VOLTTRON Home Assistant driver.
- Runs integration checks for `get_point` and `set_point`.
- Toggles the configured Home Assistant entity on and off.
"""

import json
import os

import gevent
import pytest
import requests

from volttron.platform import get_services_core
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER


ip = os.getenv("HA_IP", "localhost")
port = os.getenv("HA_PORT", "8123")
HA_TOKEN = os.getenv("HA_TOKEN")
HA_ENTITY_ID = os.getenv("HA_ENTITY_ID", "input_boolean.test_light")
HA_URL = f"http://{ip}:{port}"
HEADERS = {"Authorization": f"Bearer {HA_TOKEN}"} if HA_TOKEN else {}

HTTP_STATUS_CODES = {
    200: "Success - request worked correctly",
    201: "Created - resource was created successfully",
    202: "Accepted - request was accepted and is being processed",
    400: "Bad Request - request payload or parameters are invalid",
    401: "Unauthorized - token is missing, invalid, or expired",
    403: "Forbidden - token is valid but lacks permission",
    404: "Not Found - entity ID or endpoint was not found",
    405: "Method Not Allowed - wrong HTTP method was used",
    409: "Conflict - request conflicts with current entity state",
    422: "Unprocessable Entity - payload format was understood but rejected",
    429: "Too Many Requests - rate limit or throttling was triggered",
    500: "Internal Server Error - Home Assistant failed internally",
    502: "Bad Gateway - upstream service returned an invalid response",
    503: "Service Unavailable - Home Assistant is starting or unavailable",
    504: "Gateway Timeout - upstream service took too long to respond",
}

driver_config_dict_string = """{
    "driver_config": {
        "ip_address": "%s",
        "access_token": "%s",
        "port": "%s"
    },
    "driver_type": "home_assistant",
    "registry_config": "config://home_assistant_registry.json",
    "interval": 5,
    "timezone": "UTC"
}""" % (ip, HA_TOKEN, port)

registry_config_string = """[
    {
        "Entity ID": "%s",
        "Entity Point": "state",
        "Volttron Point Name": "test_light",
        "Units": "On / Off",
        "Units Details": "off: 0, on: 1",
        "Writable": true,
        "Starting Value": 0,
        "Type": "int",
        "Notes": "Home Assistant integration test point"
    }
]""" % HA_ENTITY_ID


def status_message(code):
    return HTTP_STATUS_CODES.get(code, "Unknown status code")


def print_banner(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def print_step(label, detail):
    print(f"[STEP] {label}: {detail}")


def print_success(label, detail):
    print(f"[PASS] {label}: {detail}")


def print_result(label, detail):
    print(f"[RESULT] {label}: {detail}")


def verify_homeassistant_access():
    print_banner("HOME ASSISTANT PREFLIGHT CHECK")
    print_step("Authorization", "checking Home Assistant API token")
    response = requests.get(
        f"{HA_URL}/api/states/{HA_ENTITY_ID}",
        headers=HEADERS,
        timeout=15,
    )
    message = status_message(response.status_code)
    print_result("Home Assistant HTTP status", f"{response.status_code} - {message}")

    if response.status_code != 200:
        pytest.fail(
            f"Home Assistant call failed with {response.status_code} - {message}. "
            f"Response body: {response.text}"
        )

    payload = response.json()
    print_success("Authorization", "success")
    print_success("Home Assistant call", "success")
    print_result("Entity ID", HA_ENTITY_ID)
    print_result("Current Home Assistant state", payload.get("state"))
    return payload


def wait_for_rpc_value(agent, expected_value, timeout=20):
    deadline = gevent.Timeout.start_new(timeout)
    try:
        while True:
            current = agent.vip.rpc.call(
                PLATFORM_DRIVER,
                "get_point",
                "home/homeassistant",
                "test_light",
            ).get(timeout=10)
            if current == expected_value:
                return current
            gevent.sleep(1)
    finally:
        deadline.cancel()


@pytest.fixture(scope="module")
def agent(request, volttron_instance_zmq):
    if not HA_TOKEN:
        pytest.skip("HA_TOKEN must be set for Home Assistant integration tests")

    if not volttron_instance_zmq.auth_enabled:
        pytest.skip("This integration test requires auth-enabled ZMQ")

    agent = volttron_instance_zmq.build_agent(identity="test_homeassistant_agent")

    capabilities = {"edit_config_store": {"identity": PLATFORM_DRIVER}}
    volttron_instance_zmq.add_capabilities(agent.core.publickey, capabilities)

    agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "delete_store",
        PLATFORM_DRIVER,
    ).get(timeout=10)

    agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "set_config",
        PLATFORM_DRIVER,
        "devices/home/homeassistant",
        driver_config_dict_string,
        "json",
    ).get(timeout=10)

    agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "set_config",
        PLATFORM_DRIVER,
        "home_assistant_registry.json",
        registry_config_string,
        "json",
    ).get(timeout=10)

    loaded = agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "list_configs",
        PLATFORM_DRIVER,
    ).get(timeout=10)
    print_result("Platform driver configs loaded", loaded)

    platform_uuid = volttron_instance_zmq.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={},
        start=True,
    )
    print_result("PlatformDriverAgent UUID", platform_uuid)
    print_result("Home Assistant URL", HA_URL)
    print_result("Home Assistant entity ID", HA_ENTITY_ID)

    gevent.sleep(5)

    def stop():
        print_step("Cleanup", "resetting test_light to off if possible")
        try:
            agent.vip.rpc.call(
                PLATFORM_DRIVER,
                "set_point",
                "home/homeassistant",
                "test_light",
                0,
            ).get(timeout=20)
        except Exception as exc:
            print_result("Cleanup reset warning", str(exc))
        print_step("Cleanup", "stopping test fixtures")
        volttron_instance_zmq.stop_agent(platform_uuid)
        agent.core.stop()

    request.addfinalizer(stop)
    return agent


def test_homeassistant_get_point_rpc(agent):
    verify_homeassistant_access()
    print_banner("TEST: platform.driver.get_point")
    peers = agent.vip.peerlist().get(timeout=10)
    print_result("Available peers", peers)
    assert PLATFORM_DRIVER in peers, "PlatformDriverAgent not found in peers"

    configs = agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "list_configs",
        PLATFORM_DRIVER,
    ).get(timeout=10)
    print_result("Platform driver configs", configs)
    assert "devices/home/homeassistant" in configs, "Device config not found"

    print_step(
        "Running get_point",
        "calling platform.driver.get_point('home/homeassistant', 'test_light')",
    )
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER,
        "get_point",
        "home/homeassistant",
        "test_light",
    ).get(timeout=20)

    print_result("get_point result", result)
    assert result in [0, 1, "on", "off"], f"Unexpected result: {result}"
    print_success("get_point", "success")


def test_homeassistant_set_point_on_rpc(agent):
    verify_homeassistant_access()
    print_banner("TEST: platform.driver.set_point -> ON")
    print_step(
        "Running set_point",
        "calling platform.driver.set_point('home/homeassistant', 'test_light', 1)",
    )
    set_result = agent.vip.rpc.call(
        PLATFORM_DRIVER,
        "set_point",
        "home/homeassistant",
        "test_light",
        1,
    ).get(timeout=20)

    print_result("set_point return value", set_result)
    observed = wait_for_rpc_value(agent, 1)
    print_result("get_point after set_point(1)", observed)
    assert observed == 1, f"Expected test_light to be 1 after set_point, got {observed}"
    print_success("set_point(1)", "success")


def test_homeassistant_set_point_off_rpc(agent):
    verify_homeassistant_access()
    print_banner("TEST: platform.driver.set_point -> OFF")
    print_step(
        "Running set_point",
        "calling platform.driver.set_point('home/homeassistant', 'test_light', 0)",
    )
    set_result = agent.vip.rpc.call(
        PLATFORM_DRIVER,
        "set_point",
        "home/homeassistant",
        "test_light",
        0,
    ).get(timeout=20)

    print_result("set_point return value", set_result)
    observed = wait_for_rpc_value(agent, 0)
    print_result("get_point after set_point(0)", observed)
    assert observed == 0, f"Expected test_light to be 0 after set_point, got {observed}"
    print_success("set_point(0)", "success")
