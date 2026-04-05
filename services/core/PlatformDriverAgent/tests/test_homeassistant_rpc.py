# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2023 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

import pytest
import gevent
import json
from gevent import pywsgi

from volttron.platform import get_services_core
from volttrontesting.utils.utils import get_rand_http_address
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER

# Set up mock Home Assistant server
server_addr = get_rand_http_address()
no_scheme = server_addr[7:]
ip, port = no_scheme.split(':')

# Mock Home Assistant state responses
HA_ENTITY_STATE = {"state": "on"}
HA_ACCESS_TOKEN = "test_token_12345"

# Device configuration for Home Assistant driver
driver_config_dict_string = """{
    "driver_config": {
        "ip_address": "%s",
        "access_token": "%s",
        "port": "%s"
    },
    "driver_type": "home_assistant",
    "registry_config": "config://home_assistant_registry.json",
    "interval": 30,
    "timezone": "UTC"
}""" % (ip, HA_ACCESS_TOKEN, port)

# Registry configuration for Home Assistant
# Maps Home Assistant entity ID to VOLTTRON point names  
registry_config_string = """[
    {
        "Entity ID": "input_boolean.test_light",
        "Entity Point": "state",
        "Volttron Point Name": "test_light",
        "Units": "On / Off",
        "Writable": false,
        "Starting Value": "on",
        "Type": "string",
        "Notes": "test light entity for unit testing"
    }
]"""


def handle_ha_request(env, start_response):
    """Mock Home Assistant API request handler"""
    path = env['PATH_INFO']
    method = env['REQUEST_METHOD']
    
    # Check authorization header
    auth = env.get('HTTP_AUTHORIZATION', '')
    if f"Bearer {HA_ACCESS_TOKEN}" not in auth:
        start_response('401 Unauthorized', [('Content-Type', 'application/json')])
        return [json.dumps({"error": "Unauthorized"}).encode()]
    
    # Handle /api/states/input_boolean.test_light
    if path == '/api/states/input_boolean.test_light' and method == 'GET':
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps(HA_ENTITY_STATE).encode()]
    
    # Default: 404
    start_response('404 Not Found', [('Content-Type', 'application/json')])
    return [json.dumps({"error": "Not found"}).encode()]


@pytest.fixture(scope='module')
def agent(request, volttron_instance):
    """Fixture that sets up Home Assistant driver test environment"""
    
    # Build a test agent
    agent = volttron_instance.build_agent()
    
    # Grant config store edit capability for platform driver
    capabilities = {'edit_config_store': {'identity': PLATFORM_DRIVER}}
    volttron_instance.add_capabilities(agent.core.publickey, capabilities)
    
    # Clean out any existing platform driver configurations
    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'delete_store',
                       PLATFORM_DRIVER).get(timeout=10)
    
    # Add device configuration
    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'set_config',
                       PLATFORM_DRIVER,
                       "devices/home/homeassistant",
                       driver_config_dict_string,
                       "json").get(timeout=10)
    
    # Add registry configuration
    agent.vip.rpc.call(CONFIGURATION_STORE,
                       'set_config',
                       PLATFORM_DRIVER,
                       "home_assistant_registry.json",
                       registry_config_string,
                       "json").get(timeout=10)
    
    # Verify configs are loaded
    print("Configs loaded:", agent.vip.rpc.call(
        CONFIGURATION_STORE,
        'list_configs',
        PLATFORM_DRIVER
    ).get(timeout=10))
    
    # Install and start PlatformDriverAgent
    platform_uuid = volttron_instance.install_agent(
        agent_dir=get_services_core("PlatformDriverAgent"),
        config_file={},
        start=True)
    print("PlatformDriverAgent UUID:", platform_uuid)
    
    gevent.sleep(2)  # Wait for agent to start
    
    # Start mock Home Assistant server
    server = pywsgi.WSGIServer((ip, int(port)), handle_ha_request)
    server.start()
    print(f"Mock Home Assistant server started at {server_addr}")
    
    def stop():
        """Cleanup"""
        print("Stopping test fixtures...")
        volttron_instance.stop_agent(platform_uuid)
        agent.core.stop()
        server.stop()
    
    request.addfinalizer(stop)
    return agent


def test_homeassistant_get_point_rpc(agent):
    """Test that platform.driver.get_point works with Home Assistant driver"""
    
    # Give the driver time to initialize and scrape
    gevent.sleep(5)
    
    # Check that PlatformDriverAgent is running
    peers = agent.vip.peerlist().get(timeout=10)
    print("\n=== Peers before get_point ===")
    print("Available peers:", peers)
    assert PLATFORM_DRIVER in peers, "PlatformDriverAgent not found in peers!"
    
    # Check that device config is loaded
    configs = agent.vip.rpc.call(
        CONFIGURATION_STORE,
        "list_configs",
        PLATFORM_DRIVER
    ).get(timeout=10)
    print("\n=== Platform Driver Configs ===")
    print("Configs:", configs)
    assert "devices/home/homeassistant" in configs, "Device config not found!"
    
    # Call get_point through platform driver
    print("\n=== TEST: Home Assistant get_point RPC Call ===")
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER,
        "get_point",
        "home/homeassistant",
        "test_light"
    ).get(timeout=20)
    
    print(f"Result: {result}")
    assert result in ["on", "off", 0, 1], f"Unexpected result: {result}"
    print("✓ Test passed! RPC returned:", result)