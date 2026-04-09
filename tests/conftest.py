"""Shared fixtures for ntfy-blade-mcp tests."""

from __future__ import annotations

import pytest

from ntfy_blade_mcp.models import NtfyConfig


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no real env vars leak into tests."""
    for key in ("NTFY_BASE_URL", "NTFY_TOKEN", "NTFY_DEFAULT_TOPIC", "NTFY_WRITE_ENABLED", "TRANSPORT"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture()
def write_config() -> NtfyConfig:
    """Config with writes enabled."""
    return NtfyConfig(
        base_url="https://ntfy.example.com",
        token="tk_test1234567890abcdef",
        default_topic="test-topic",
        write_enabled=True,
    )


@pytest.fixture()
def readonly_config() -> NtfyConfig:
    """Config with writes disabled (default)."""
    return NtfyConfig(
        base_url="https://ntfy.example.com",
        token="tk_test1234567890abcdef",
        default_topic="test-topic",
        write_enabled=False,
    )
