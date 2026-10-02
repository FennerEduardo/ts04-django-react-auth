from app.infrastructure.event_bus import EventBus


def test_publish_delivers_to_subscribers_and_records_history():
    bus = EventBus()
    received = []
    bus.subscribe("Ping", received.append)
    bus.publish("Ping", {"n": 1})
    assert received == [{"n": 1}]
    assert bus.published == [("Ping", {"n": 1})]
