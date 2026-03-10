
import tools.bridge.consumer as consumer


def test_consumer_bootstrap_on_mbp(monkeypatch):
    monkeypatch.setattr(consumer.socket, "gethostname", lambda: "MBP-Pro-Max")

    called = False

    def fake_main():
        nonlocal called
        called = True

    monkeypatch.setattr(consumer, "main", fake_main)
    consumer.main()

    assert called is True
