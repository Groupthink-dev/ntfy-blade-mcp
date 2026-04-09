"""Tests for the ntfy HTTP client using respx mocking."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from ntfy_blade_mcp.client import NtfyClient
from ntfy_blade_mcp.models import AuthError, NtfyConfig, ServerError


@pytest.fixture()
def config() -> NtfyConfig:
    return NtfyConfig(
        base_url="https://ntfy.test",
        token="tk_testtoken1234567890",
    )


@pytest.fixture()
def client(config: NtfyConfig) -> NtfyClient:
    return NtfyClient(config)


class TestHealth:
    @respx.mock
    async def test_healthy(self, client: NtfyClient) -> None:
        respx.get("https://ntfy.test/v1/health").mock(return_value=httpx.Response(200, json={"healthy": True}))
        result = await client.health()
        assert result["healthy"] is True

    @respx.mock
    async def test_server_error(self, client: NtfyClient) -> None:
        respx.get("https://ntfy.test/v1/health").mock(return_value=httpx.Response(500, text="Internal Server Error"))
        with pytest.raises(ServerError):
            await client.health()


class TestConfig:
    @respx.mock
    async def test_config(self, client: NtfyClient) -> None:
        respx.get("https://ntfy.test/v1/config").mock(
            return_value=httpx.Response(200, json={"base_url": "https://ntfy.test", "enable_signup": True})
        )
        result = await client.config()
        assert result["base_url"] == "https://ntfy.test"


class TestStats:
    @respx.mock
    async def test_stats(self, client: NtfyClient) -> None:
        respx.get("https://ntfy.test/v1/stats").mock(
            return_value=httpx.Response(200, json={"messages": 42, "messages_rate": 1.5})
        )
        result = await client.stats()
        assert result["messages"] == 42


class TestPublish:
    @respx.mock
    async def test_publish(self, client: NtfyClient) -> None:
        respx.post("https://ntfy.test/").mock(
            return_value=httpx.Response(200, json={"id": "msg123", "topic": "alerts", "expires": 999})
        )
        result = await client.publish({"topic": "alerts", "message": "hello"})
        assert result["id"] == "msg123"

    @respx.mock
    async def test_auth_error(self, client: NtfyClient) -> None:
        respx.post("https://ntfy.test/").mock(return_value=httpx.Response(403, text="Forbidden"))
        with pytest.raises(AuthError):
            await client.publish({"topic": "secret", "message": "nope"})


class TestCancel:
    @respx.mock
    async def test_cancel(self, client: NtfyClient) -> None:
        respx.delete("https://ntfy.test/alerts/msg123").mock(
            return_value=httpx.Response(200, json={"id": "msg123", "event": "message_delete"})
        )
        result = await client.cancel("alerts", "msg123")
        assert result["event"] == "message_delete"


class TestPoll:
    @respx.mock
    async def test_poll_messages(self, client: NtfyClient) -> None:
        ndjson = "\n".join(
            [
                json.dumps({"event": "message", "id": "a", "message": "first"}),
                json.dumps({"event": "message", "id": "b", "message": "second"}),
            ]
        )
        respx.get("https://ntfy.test/alerts/json").mock(return_value=httpx.Response(200, text=ndjson))
        messages = await client.poll("alerts", since="10m")
        assert len(messages) == 2
        assert messages[0]["id"] == "a"

    @respx.mock
    async def test_poll_empty(self, client: NtfyClient) -> None:
        respx.get("https://ntfy.test/alerts/json").mock(return_value=httpx.Response(200, text=""))
        messages = await client.poll("alerts")
        assert messages == []

    @respx.mock
    async def test_poll_filters_non_message_events(self, client: NtfyClient) -> None:
        ndjson = "\n".join(
            [
                json.dumps({"event": "open"}),
                json.dumps({"event": "message", "id": "a", "message": "real"}),
                json.dumps({"event": "keepalive"}),
            ]
        )
        respx.get("https://ntfy.test/alerts/json").mock(return_value=httpx.Response(200, text=ndjson))
        messages = await client.poll("alerts")
        assert len(messages) == 1


class TestReservations:
    @respx.mock
    async def test_reserve(self, client: NtfyClient) -> None:
        respx.post("https://ntfy.test/v1/account/reservation").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await client.reserve("my-topic", "deny-all")
        assert result.get("success") is True

    @respx.mock
    async def test_unreserve(self, client: NtfyClient) -> None:
        respx.delete("https://ntfy.test/v1/account/reservation/my-topic").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await client.unreserve("my-topic")
        assert result.get("success") is True


class TestTokens:
    @respx.mock
    async def test_token_create(self, client: NtfyClient) -> None:
        respx.post("https://ntfy.test/v1/account/token").mock(
            return_value=httpx.Response(200, json={"token": "tk_new1234567890abcdef", "label": "test", "expires": 999})
        )
        result = await client.token_create(label="test")
        assert result["token"].startswith("tk_")

    @respx.mock
    async def test_token_extend(self, client: NtfyClient) -> None:
        respx.patch("https://ntfy.test/v1/account/token").mock(
            return_value=httpx.Response(200, json={"token": "tk_existing", "expires": 2000})
        )
        result = await client.token_extend("tk_existing", expires=2000)
        assert result["expires"] == 2000

    @respx.mock
    async def test_token_revoke(self, client: NtfyClient) -> None:
        respx.delete("https://ntfy.test/v1/account/token").mock(
            return_value=httpx.Response(200, json={"success": True})
        )
        result = await client.token_revoke("tk_old12345678901234567")
        assert result.get("success") is True
