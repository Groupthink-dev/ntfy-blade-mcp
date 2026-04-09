"""Tests for models: config, gates, validation, PII scrubbing."""

from __future__ import annotations

import pytest

from ntfy_blade_mcp.models import (
    NtfyConfig,
    check_confirm_gate,
    check_write_gate,
    resolve_config,
    resolve_topic,
    scrub_pii,
    validate_topic,
)


class TestResolveConfig:
    def test_defaults(self) -> None:
        config = resolve_config()
        assert config.base_url == "https://ntfy.sh"
        assert config.token is None
        assert config.default_topic is None
        assert config.write_enabled is False
        assert config.transport == "stdio"

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NTFY_BASE_URL", "https://my-ntfy.example.com/")
        monkeypatch.setenv("NTFY_TOKEN", "tk_abc123")
        monkeypatch.setenv("NTFY_DEFAULT_TOPIC", "alerts")
        monkeypatch.setenv("NTFY_WRITE_ENABLED", "true")
        monkeypatch.setenv("TRANSPORT", "http")
        config = resolve_config()
        assert config.base_url == "https://my-ntfy.example.com"  # trailing slash stripped
        assert config.token == "tk_abc123"
        assert config.default_topic == "alerts"
        assert config.write_enabled is True
        assert config.transport == "http"


class TestWriteGate:
    def test_disabled(self) -> None:
        config = NtfyConfig(write_enabled=False)
        assert check_write_gate(config) is not None
        assert "disabled" in check_write_gate(config).lower()  # type: ignore[union-attr]

    def test_enabled(self) -> None:
        config = NtfyConfig(write_enabled=True)
        assert check_write_gate(config) is None


class TestConfirmGate:
    def test_not_confirmed(self) -> None:
        result = check_confirm_gate(False, "Sending")
        assert result is not None
        assert "confirm=true" in result

    def test_confirmed(self) -> None:
        assert check_confirm_gate(True, "Sending") is None


class TestValidateTopic:
    @pytest.mark.parametrize("topic", ["alerts", "my-topic", "test_123", "A" * 64])
    def test_valid(self, topic: str) -> None:
        assert validate_topic(topic) is None

    @pytest.mark.parametrize("topic", ["", "a/b", "has space", "A" * 65, "emoji🔔"])
    def test_invalid(self, topic: str) -> None:
        assert validate_topic(topic) is not None


class TestResolveTopic:
    def test_explicit(self) -> None:
        config = NtfyConfig(default_topic="fallback")
        err, topic = resolve_topic("explicit", config)
        assert err is None
        assert topic == "explicit"

    def test_default(self) -> None:
        config = NtfyConfig(default_topic="fallback")
        err, topic = resolve_topic(None, config)
        assert err is None
        assert topic == "fallback"

    def test_no_topic(self) -> None:
        config = NtfyConfig()
        err, topic = resolve_topic(None, config)
        assert err is not None
        assert "NTFY_DEFAULT_TOPIC" in err


class TestScrubPii:
    def test_scrub_token(self) -> None:
        text = "Auth failed with tk_AgQdq7mVBoFD37zQVN29RhuMzNIz2"
        assert "[REDACTED_TOKEN]" in scrub_pii(text)
        assert "tk_" not in scrub_pii(text)

    def test_scrub_bearer(self) -> None:
        text = "Header: Bearer tk_secret123456789012345"
        result = scrub_pii(text)
        assert "Bearer [REDACTED]" in result

    def test_clean_text_unchanged(self) -> None:
        text = "No secrets here"
        assert scrub_pii(text) == text
