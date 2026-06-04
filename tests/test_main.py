from unittest.mock import Mock

from sakai_bot.main import notify_fallback


def test_notify_fallback_sends_when_reason_present():
    telegram = Mock()
    sent = notify_fallback(telegram, "level filter matched nothing", 3)
    assert sent is True
    telegram.send_message.assert_called_once()
    assert "level filter matched nothing" in telegram.send_message.call_args[0][0]


def test_notify_fallback_noop_without_reason():
    telegram = Mock()
    sent = notify_fallback(telegram, None, 5)
    assert sent is False
    telegram.send_message.assert_not_called()


def test_notify_fallback_swallows_send_errors():
    telegram = Mock()
    telegram.send_message.side_effect = RuntimeError("network down")
    sent = notify_fallback(telegram, "some reason", 1)
    assert sent is False
