import json
import logging

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import JsonFormatter, request_id_var

BASE = {
    "SECRET_KEY": "k" * 32,
    "SECRET_PEPPER": "p" * 32,
}


def make(**overrides) -> Settings:
    return Settings(_env_file=None, **{**BASE, **overrides})


def test_public_url_is_normalized_to_origin():
    assert (
        make(PUBLIC_URL="https://aroundfm.example/some/path").PUBLIC_URL
        == "https://aroundfm.example"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"ENVIRONMENT": "production", "PUBLIC_URL": "http://aroundfm.example"},
        {"ENVIRONMENT": "production", "PUBLIC_URL": "https://a.example", "COOKIE_SECURE": False},
        {"ENVIRONMENT": "production", "PUBLIC_URL": "https://a.example", "SEED_DEMO_USERS": True},
        {"PUBLIC_URL": "ftp://x"},
        {"BOT_API_SECRET": "short"},
        {"SECRET_KEY": "short"},
    ],
)
def test_invalid_settings_rejected(overrides):
    with pytest.raises(ValidationError):
        make(**overrides)


def test_production_settings_accepted():
    s = make(ENVIRONMENT="production", PUBLIC_URL="https://a.example")
    assert s.is_production


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://a.example, https://b.example", ["https://a.example", "https://b.example"]),
        ('["https://a.example"]', ["https://a.example"]),
    ],
)
def test_cors_origins_parsing(raw, expected):
    assert expected == make(CORS_ORIGINS=raw).CORS_ORIGINS


def test_optional_integrations_empty_strings_disable_them():
    s = make(TELEGRAM_BOT_TOKEN="", BOT_API_SECRET="")
    assert not s.telegram_enabled
    assert s.BOT_API_SECRET is None


def test_json_log_formatter_includes_request_id():
    token = request_id_var.set("req-1")
    try:
        record = logging.LogRecord("x", logging.INFO, __file__, 1, "hello %s", ("world",), None)
        record.request_id = request_id_var.get()
        record.status = 200
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["msg"] == "hello world"
    assert payload["request_id"] == "req-1"
    assert payload["status"] == 200
