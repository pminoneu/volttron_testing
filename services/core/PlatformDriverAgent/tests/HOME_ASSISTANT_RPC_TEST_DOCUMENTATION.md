# Home Assistant RPC Integration Test Documentation

## Overview

This test verifies that **VOLTTRON can successfully communicate with Home Assistant** through the refactored Home Assistant driver architecture. It tests the complete integration flow from an RPC call through VOLTTRON's PlatformDriverAgent to Home Assistant's REST API.

**Test File:** `test_homeassistant_rpc.py`

**Test Function:** `test_homeassistant_get_point_rpc()`

---

## What This Test Does

### High-Level Flow

```
Test Agent
    ↓ (RPC call)
PlatformDriverAgent (installed in temporary VOLTTRON)
    ↓ (routes to handler)
Home Assistant Driver (home_assistant.py)
    ↓ (selects appropriate handler)
Handler (e.g., InputBooleanHandler)
    ↓ (HTTP request)
Home Assistant API
    ↓ (returns entity state)
Test Agent (receives result)
    ↓ (verifies correctness)
PASSED ✓
```

### Step-by-Step Execution

1. **Creates a temporary VOLTTRON platform** - Isolated test environment with its own configuration store, keystore, and message bus
2. **Installs PlatformDriverAgent** - The core driver agent that manages device communication
3. **Configures Home Assistant connection** - Sets device config (IP, token, port) and registry mapping
4. **Makes RPC call** - `platform.driver.get_point("home/homeassistant", "test_light")`
5. **Driver processes request:**
   - Looks up register by point name
   - Extracts entity ID (`input_boolean.test_light`)
   - Routes to correct handler based on domain (`input_boolean`)
   - Handler makes HTTP GET to Home Assistant
6. **Receives response** - Entity state returned (e.g., `0` for "off", `1` for "on")
7. **Validates result** - Asserts value is in expected set `["on", "off", 0, 1]`

---

## What It Tests

### ✅ Architecture Components Tested

1. **Device Configuration Parsing** (`home_assistant.py:configure()`)
   - Requires: ip_address, access_token, port
   - Validates: All required fields present

2. **Registry Configuration** (JSON array format)
   - Entity ID mapping
   - Entity Point specification
   - VOLTTRON Point Name creation

3. **Handler Routing** (`home_assistant.py:_get_handler()`)
   - Extracts domain from entity ID (e.g., "input_boolean" from "input_boolean.test_light")
   - Routes to correct handler (InputBooleanHandler for input_boolean entities)

4. **Data Scraping** (`homeassistant_handlers/input_boolean.py:scrape()`)
   - Makes HTTP GET request to HA API
   - Parses entity state response
   - Converts state to appropriate type (`on`/`off` → 1/0)

5. **HTTP Communication** (`home_assistant.py:get_entity_data()`)
   - Builds correct API URL: `/api/states/{entity_id}`
   - Includes Bearer token authentication
   - Handles HTTP status codes

6. **VOLTTRON Integration**
   - RPC interface works correctly
   - Config store integration
   - Agent lifecycle management

### ❌ What It Does NOT Test

- `set_point()` - Writing/controlling devices
- Other entity handlers (light, climate, lock, switch)
- Error handling and edge cases
- Handler service calls (turn_on, turn_off, etc.)
- Multiple simultaneous requests
- Rate limiting or performance

---

## How to Run

### Quick Test (Mock Home Assistant)

```bash
cd /home/paula-minozzo/volttron_testing
source env/bin/activate
python -m pytest services/core/PlatformDriverAgent/tests/test_homeassistant_rpc.py::test_homeassistant_get_point_rpc -s
```

**Output:** Quick test with built-in mock HA server

### Full Integration Test (Real Home Assistant)

```bash
export HA_TOKEN="your_long_lived_access_token"
export HA_IP="localhost"
export HA_PORT="8123"
export HA_ENTITY_ID="input_boolean.test_light"

cd /home/paula-minozzo/volttron_testing
source env/bin/activate
python -m pytest services/core/PlatformDriverAgent/tests/test_homeassistant_rpc.py::test_homeassistant_get_point_rpc -s -v
```

**Output:** Real integration test connecting to actual Home Assistant instance

### Run All Tests

```bash
python -m pytest services/core/PlatformDriverAgent/tests/test_homeassistant_rpc.py -s -v
```

---

## Test Modes

### Mode 1: Mock Home Assistant (Default)

**When:** `HA_TOKEN` environment variable is NOT set

**What happens:**
- Test creates fake Home Assistant API server
- Runs on random local port
- Returns hardcoded responses
- Useful for: CI/CD, automated testing, no external dependencies

**Trade-off:** Does not test against real HA implementation details

### Mode 2: Real Home Assistant

**When:** `HA_TOKEN` environment variable IS set

**What happens:**
- Connects to real Home Assistant at `localhost:8123`
- Uses provided token for authentication
- Queries actual entity from your HA instance
- Returns real entity state

**Trade-off:** Requires HA to be running, but validates against real system

---

## Test Output Example

### Successful Test
```
TEST MODE: Real Home Assistant
  HA Address: http://localhost:8123
  Entity ID: input_boolean.test_light

=== Peers before get_point ===
Available peers: ['platform.driver', '57e07c06-611d-41b8-b010-239113daf40b', 'dynamic_agent', ...]

=== Platform Driver Configs ===
Configs: ['devices/home/homeassistant', 'home_assistant_registry.json']

=== TEST: Home Assistant get_point RPC Call ===
Calling: platform.driver.get_point('home/homeassistant', 'test_light')
Result: 0
✓ Test passed! RPC returned: 0
PASSED
```

### Failed Test - Missing HA
```
Calling: platform.driver.get_point('home/homeassistant', 'test_light')
...
requests.exceptions.ConnectionError: Failed to connect to http://localhost:8123/api/states/input_boolean.test_light
```

### Failed Test - Bad Token
```
WARNING (MainThread) [homeassistant.components.http.ban] Login attempt or request with invalid authentication from 172.17.0.1
...
AssertionError: Request failed with status code 401, entity_id: input_boolean.test_light
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ VOLTTRON Platform (temporary, in VM)                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Test Agent                                           │  │
│  │ - Makes RPC call                                     │  │
│  │ - Receives data                                      │  │
│  │ - Validates result                                   │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │ RPC: get_point()                        │
│                   ↓                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ PlatformDriverAgent (platform.driver)                │  │
│  │ - Manages device configs                             │  │
│  │ - Routes RPC calls                                   │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ↓                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Home Assistant Driver (home_assistant.py)            │  │
│  │ - Parses device config                               │  │
│  │ - Routes by entity domain                            │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
│                   ↓                                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Handler (homeassistant_handlers/input_boolean.py)    │  │
│  │ - Calls scrape()                                     │  │
│  │ - Normalizes state (on/off → 1/0)                    │  │
│  └────────────────┬─────────────────────────────────────┘  │
│                   │                                          │
└───────────────────┼──────────────────────────────────────────┘
                    │
                    │ HTTP GET /api/states/input_boolean.test_light
                    │ Bearer: {token}
                    ↓
┌─────────────────────────────────────────────────────────────┐
│ Home Assistant (real or mock)                               │
│ Returns: {"state": "on"}                                    │
└─────────────────────────────────────────────────────────────┘
```

---

## Configuration Details

### Device Configuration (JSON)
```json
{
    "driver_config": {
        "ip_address": "localhost",
        "access_token": "eyJh...",
        "port": "8123"
    },
    "driver_type": "home_assistant",
    "registry_config": "config://home_assistant_registry.json",
    "interval": 30,
    "timezone": "UTC"
}
```

### Registry Configuration (JSON Array)
```json
[
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
]
```

---

## Creating Your HA Token

1. Go to Home Assistant UI: `http://localhost:8123`
2. Click your profile (bottom-left avatar)
3. Scroll to **Long-Lived Access Tokens**
4. Click **Create Token**
5. Name it (e.g., "VOLTTRON Test")
6. Copy the token (it looks like `eyJh...`)

**Keep this token safe!** Do not commit to git.

---

## Known Issues & Limitations

1. **Multiple test instances** - pytest runs this test with 3 different VOLTTRON instances by default. The first passes, others may fail due to auth issues (unrelated to the driver).

2. **Mock server limitations** - Mock returns same state for all entities, doesn't track state changes

3. **Timeout issues** - If HA is slow, test may timeout (default 20 seconds)

4. **Token expiration** - Tokens expire over time, will need regeneration

---

## Future Test Expansion

### Recommended Additions

1. **Test set_point** - Verify turning devices on/off works
2. **Test light entity** - Verify handler for `light.` entities
3. **Test climate entity** - Verify handler for `climate.` entities  
4. **Error handling** - Test 401 Unauthorized, 404 Not Found, etc.
5. **State change verification** - Toggle light on/off and verify state updated
6. **Performance** - Test with multiple points/devices

### Example: Testing set_point
```python
def test_homeassistant_set_point_rpc(agent):
    """Test setting an input_boolean state through VOLTTRON"""
    # Current state
    current = agent.vip.rpc.call(PLATFORM_DRIVER, "get_point", 
                                 "home/homeassistant", "test_light").get(timeout=20)
    
    # Toggle the state
    new_state = 1 if current == 0 else 0
    result = agent.vip.rpc.call(PLATFORM_DRIVER, "set_point",
                                "home/homeassistant", "test_light", new_state).get(timeout=20)
    
    # Verify it changed
    verify = agent.vip.rpc.call(PLATFORM_DRIVER, "get_point",
                                "home/homeassistant", "test_light").get(timeout=20)
    assert verify == new_state
```

---

## References

- [VOLTTRON Platform Driver Documentation](https://volttron.readthedocs.io/en/main/agent-framework/driver-framework/platform-driver/platform-driver-agent.html)
- [Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest)
- [Home Assistant Long-Lived Access Tokens](https://developers.home-assistant.io/docs/auth_api/#long-lived-access-token)
- [VOLTTRON Home Assistant Driver](../platform_driver/interfaces/home_assistant.py)
- [Handler Implementation](../platform_driver/interfaces/homeassistant_handlers/)

---

## Author Notes

**Test Created:** April 2026  
**Last Updated:** April 5, 2026  
**Status:** ✅ Working - verified with real Home Assistant  
**Branch:** `paula/integration-tests-clean`

This test validates the refactored Home Assistant driver architecture and exercises the handler-based design pattern introduced by your team's refactoring.
