
import pytest
import gevent
import json
import os
from gevent import pywsgi

from volttron.platform import get_services_core
from volttrontesting.utils.utils import get_rand_http_address
from volttron.platform.agent.known_identities import CONFIGURATION_STORE, PLATFORM_DRIVER

# Check if using real Home Assistant or mock
USE_REAL_HA = os.getenv("HA_TOKEN") is not None
HA_ENTITY_ID = os.getenv("HA_ENTITY_ID", "input_boolean.test_light")

if USE_REAL_HA:
    # Real Home Assistant connection
    ip = os.getenv("HA_IP", "localhost")
    port = os.getenv("HA_PORT", "8123")
    HA_TOKEN = os.getenv("HA_TOKEN")
    mock_server = None
else:
    # Mock Home Assistant server
    server_addr = get_rand_http_address()
    no_scheme = server_addr[7:]
    ip, port = no_scheme.split(':')
    HA_TOKEN = "test_token_12345"
    mock_server = None

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
}""" % (ip, HA_TOKEN, port)

# Registry configuration for Home Assistant
# Maps Home Assistant entity ID to VOLTTRON point names  
registry_config_string = """[
    {
        "Entity ID": "%s",
        "Entity Point": "state",
        "Volttron Point Name": "test_light",
        "Units": "On / Off",
        "Writable": false,
        "Starting Value": "on",
        "Type": "string",
        "Notes": "test light entity for unit testing"
    }
]""" % HA_ENTITY_ID


def handle_ha_request(env, start_response):
    """Mock Home Assistant API request handler"""
    path = env['PATH_INFO']
    method = env['REQUEST_METHOD']
    
    # Check authorization header
    auth = env.get('HTTP_AUTHORIZATION', '')
    if f"Bearer {HA_TOKEN}" not in auth:
        start_response('401 Unauthorized', [('Content-Type', 'application/json')])
        return [json.dumps({"error": "Unauthorized"}).encode()]
    
    # Handle any entity state request
    if path.startswith('/api/states/') and method == 'GET':
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [json.dumps({"state": "on"}).encode()]
    
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
    
    # Start mock Home Assistant server (only if not using real HA)
    server = None
    if not USE_REAL_HA:
        server = pywsgi.WSGIServer((ip, int(port)), handle_ha_request)
        server.start()
        print(f"Mock Home Assistant server started at http://{ip}:{port}")
    else:
        print(f"Using real Home Assistant at http://{ip}:{port}")
    
    def stop():
        """Cleanup"""
        print("Stopping test fixtures...")
        volttron_instance.stop_agent(platform_uuid)
        agent.core.stop()
        if server:
            server.stop()
    
    request.addfinalizer(stop)
    return agent


def test_homeassistant_get_point_rpc(agent):
    """Test that platform.driver.get_point works with Home Assistant driver"""
    
    # Give the driver time to initialize and scrape
    gevent.sleep(5)
    
    # Print which mode we're in
    print("\n" + "="*70)
    if USE_REAL_HA:
        print("TEST MODE: Real Home Assistant")
        print(f"  HA Address: http://{ip}:{port}")
        print(f"  Entity ID: {HA_ENTITY_ID}")
    else:
        print("TEST MODE: Mock Home Assistant (for CI/testing)")
    print("="*70)
    
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
    print(f"Calling: platform.driver.get_point('home/homeassistant', 'test_light')")
    result = agent.vip.rpc.call(
        PLATFORM_DRIVER,
        "get_point",
        "home/homeassistant",
        "test_light"
    ).get(timeout=20)
    
    print(f"Result: {result}")
    assert result in ["on", "off", 0, 1], f"Unexpected result: {result}"
    print("✓ Test passed! RPC returned:", result)