import pytest

from sakai_bot.config import get_settings

REQUIRED_ENV = {
    "SAKAI_USERNAME": "test_user",
    "SAKAI_PASSWORD": "test_pass",
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_SERVICE_ROLE_KEY": "test_key",
    "TELEGRAM_BOT_TOKEN": "test_token",
    "TELEGRAM_CHAT_ID": "123",
}


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch):
    """Provide dummy required env vars and a clean settings cache per test."""
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("CURRENT_SEMESTER", raising=False)
    monkeypatch.delenv("COURSE_LEVEL_FILTER", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
