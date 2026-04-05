@pytest.mark.xfail(reason="Home Assistant driver harness setup still in progress", strict=False)
def test_homeassistant_get_point_rpc(agent_fixture):
    gevent.sleep(5)
    print("Platform driver UUID:", platform_uuid)
    print("Fixture peers after install:", agent.vip.peerlist().get(timeout=10))
    print("Loaded configs:", agent.vip.rpc.call(CONFIGURATION_STORE, "list_configs", PLATFORM_DRIVER).get(timeout=10))

    peers = agent_fixture.vip.peerlist().get(timeout=10)
    print("\nPeers:", peers)

    configs = agent_fixture.vip.rpc.call(
        CONFIGURATION_STORE,
        "list_configs",
        PLATFORM_DRIVER
    ).get(timeout=10)
    print("Platform driver configs:", configs)

    result = agent_fixture.vip.rpc.call(
        PLATFORM_DRIVER,
        "get_point",
        "home/homeassistant",
        "test_light"
    ).get(timeout=20)

    print("\n=== TEST: Home Assistant get_point via PLATFORM_DRIVER ===")
    print("Result:", result)

    assert result in [0, 1, "on", "off"]