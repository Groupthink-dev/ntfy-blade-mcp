"""Tests for server tool logic (gates, validation, formatting)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from ntfy_blade_mcp.models import NtfyConfig

# We test the tool functions by patching _config and _get_client


def _make_config(write: bool = True, topic: str = "test-topic") -> NtfyConfig:
    return NtfyConfig(
        base_url="https://ntfy.test",
        token="tk_test1234567890abcdef",
        default_topic=topic,
        write_enabled=write,
    )


class TestNtfyInfo:
    async def test_info_returns_compact(self) -> None:
        mock_client = AsyncMock()
        mock_client.health.return_value = {"healthy": True}
        mock_client.config.return_value = {"base_url": "https://ntfy.test", "enable_signup": True}
        mock_client.stats.return_value = {"messages": 100, "messages_rate": 1.0}

        with (
            patch("ntfy_blade_mcp.server._get_client", return_value=mock_client),
            patch("ntfy_blade_mcp.server._config", _make_config()),
        ):
            from ntfy_blade_mcp.server import ntfy_info

            result = await ntfy_info()
            assert "healthy=yes" in result
            assert "msgs=100" in result


class TestNtfyPublish:
    async def test_write_gate_blocks(self) -> None:
        with patch("ntfy_blade_mcp.server._config", _make_config(write=False)):
            from ntfy_blade_mcp.server import ntfy_publish

            result = await ntfy_publish(message="test", confirm=True)
            assert "disabled" in result.lower()

    async def test_confirm_gate_blocks(self) -> None:
        with patch("ntfy_blade_mcp.server._config", _make_config(write=True)):
            from ntfy_blade_mcp.server import ntfy_publish

            result = await ntfy_publish(message="test", confirm=False)
            assert "confirm=true" in result

    async def test_publish_success(self) -> None:
        mock_client = AsyncMock()
        mock_client.publish.return_value = {"id": "abc123", "topic": "test-topic", "expires": 999}

        with (
            patch("ntfy_blade_mcp.server._get_client", return_value=mock_client),
            patch("ntfy_blade_mcp.server._config", _make_config(write=True)),
        ):
            from ntfy_blade_mcp.server import ntfy_publish

            result = await ntfy_publish(message="hello", confirm=True)
            assert "id=abc123" in result
            assert "topic=test-topic" in result

    async def test_too_many_actions(self) -> None:
        with patch("ntfy_blade_mcp.server._config", _make_config(write=True)):
            from ntfy_blade_mcp.server import ntfy_publish

            actions = [{"action": "view", "label": f"a{i}", "url": "https://x"} for i in range(5)]
            result = await ntfy_publish(message="test", actions=actions, confirm=True)
            assert "Maximum 3" in result


class TestNtfyPoll:
    async def test_poll_success(self) -> None:
        mock_client = AsyncMock()
        mock_client.poll.return_value = [
            {"id": "a", "time": 1, "message": "hello"},
        ]

        with (
            patch("ntfy_blade_mcp.server._get_client", return_value=mock_client),
            patch("ntfy_blade_mcp.server._config", _make_config()),
        ):
            from ntfy_blade_mcp.server import ntfy_poll

            result = await ntfy_poll()
            assert "1 message(s)" in result
            assert "hello" in result

    async def test_poll_no_topic(self) -> None:
        config = _make_config()
        config.default_topic = None
        with patch("ntfy_blade_mcp.server._config", config):
            from ntfy_blade_mcp.server import ntfy_poll

            result = await ntfy_poll()
            assert "NTFY_DEFAULT_TOPIC" in result


class TestNtfyCancel:
    async def test_cancel_requires_gates(self) -> None:
        with patch("ntfy_blade_mcp.server._config", _make_config(write=False)):
            from ntfy_blade_mcp.server import ntfy_cancel

            result = await ntfy_cancel(message_id="x", confirm=True)
            assert "disabled" in result.lower()


class TestNtfyReserve:
    async def test_invalid_acl(self) -> None:
        with patch("ntfy_blade_mcp.server._config", _make_config(write=True)):
            from ntfy_blade_mcp.server import ntfy_reserve

            result = await ntfy_reserve(topic="test", everyone="invalid", confirm=True)
            assert "Invalid ACL" in result

    async def test_invalid_topic(self) -> None:
        with patch("ntfy_blade_mcp.server._config", _make_config(write=True)):
            from ntfy_blade_mcp.server import ntfy_reserve

            result = await ntfy_reserve(topic="bad topic!", confirm=True)
            assert "Invalid topic" in result


class TestNtfyTokenCreate:
    async def test_shows_full_token(self) -> None:
        mock_client = AsyncMock()
        mock_client.token_create.return_value = {
            "token": "tk_AbCdEfGh1234567890ab",
            "label": "my-label",
            "expires": 999,
        }

        with (
            patch("ntfy_blade_mcp.server._get_client", return_value=mock_client),
            patch("ntfy_blade_mcp.server._config", _make_config(write=True)),
        ):
            from ntfy_blade_mcp.server import ntfy_token_create

            result = await ntfy_token_create(label="my-label", confirm=True)
            assert "tk_AbCdEfGh1234567890ab" in result  # full token shown on create
