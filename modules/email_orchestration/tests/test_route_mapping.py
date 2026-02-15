from modules.email_orchestration.route import route_task


def test_route_mapping_uses_ring_defaults_and_response_channel():
    routed = route_task({"task_id": "abc", "ring": "R2"}, "gg:requests")
    assert routed["lane"] == "execute"
    assert routed["request_channel"] == "gg:requests"
    assert routed["response_channel"] == "gg:responses:abc"
