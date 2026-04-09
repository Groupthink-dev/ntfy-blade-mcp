"""Async HTTP client for the ntfy API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from ntfy_blade_mcp.models import AuthError, NtfyConfig, NtfyError, ServerError, scrub_pii

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_MAX_RETRIES = 2


class NtfyClient:
    """Thin async wrapper around the ntfy HTTP API."""

    def __init__(self, config: NtfyConfig) -> None:
        self._base = config.base_url
        headers: dict[str, str] = {"Accept": "application/json"}
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self._client = httpx.AsyncClient(
            base_url=self._base,
            headers=headers,
            timeout=_TIMEOUT,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Low-level request
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Issue a request with basic error classification."""
        try:
            resp = await self._client.request(method, path, json=json, params=params)
        except httpx.TimeoutException as exc:
            raise NtfyError(f"Request to {path} timed out") from exc
        except httpx.ConnectError as exc:
            raise NtfyError(f"Cannot connect to {self._base}") from exc

        if resp.status_code in (401, 403):
            raise AuthError(f"Authentication failed ({resp.status_code}): {scrub_pii(resp.text)}")
        if resp.status_code >= 500:
            raise ServerError(f"Server error ({resp.status_code}): {resp.text[:200]}")
        if resp.status_code >= 400:
            raise NtfyError(f"Request failed ({resp.status_code}): {resp.text[:200]}")
        return resp

    # ------------------------------------------------------------------
    # Info endpoints (no auth required)
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """GET /v1/health"""
        resp = await self._request("GET", "/v1/health")
        return resp.json()  # type: ignore[no-any-return]

    async def config(self) -> dict[str, Any]:
        """GET /v1/config — server capabilities."""
        resp = await self._request("GET", "/v1/config")
        return resp.json()  # type: ignore[no-any-return]

    async def stats(self) -> dict[str, Any]:
        """GET /v1/stats — global message stats."""
        resp = await self._request("GET", "/v1/stats")
        return resp.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    async def account(self) -> dict[str, Any]:
        """GET /v1/account — limits, stats, tokens, reservations."""
        resp = await self._request("GET", "/v1/account")
        return resp.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(self, payload: dict[str, Any]) -> dict[str, Any]:
        """POST / — publish a notification (JSON body)."""
        resp = await self._request("POST", "/", json=payload)
        return resp.json()  # type: ignore[no-any-return]

    async def cancel(self, topic: str, message_id: str) -> dict[str, Any]:
        """DELETE /{topic}/{id} — cancel a scheduled message."""
        resp = await self._request("DELETE", f"/{topic}/{message_id}")
        return resp.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Poll
    # ------------------------------------------------------------------

    async def poll(
        self,
        topics: str,
        *,
        since: str | None = None,
        scheduled: bool = False,
        priority: str | None = None,
        tags: str | None = None,
    ) -> list[dict[str, Any]]:
        """GET /{topics}/json?poll=1 — fetch cached messages."""
        params: dict[str, str] = {"poll": "1"}
        if since:
            params["since"] = since
        if scheduled:
            params["scheduled"] = "1"
        if priority:
            params["priority"] = priority
        if tags:
            params["tags"] = tags

        resp = await self._request("GET", f"/{topics}/json", params=params)
        # Response is newline-delimited JSON (NDJSON)
        messages: list[dict[str, Any]] = []
        for line in resp.text.strip().splitlines():
            if not line:
                continue
            import json

            obj = json.loads(line)
            if obj.get("event") == "message":
                messages.append(obj)
        return messages

    # ------------------------------------------------------------------
    # Reservations
    # ------------------------------------------------------------------

    async def reserve(self, topic: str, everyone: str = "deny-all") -> dict[str, Any]:
        """POST /v1/account/reservation — reserve a topic."""
        resp = await self._request("POST", "/v1/account/reservation", json={"topic": topic, "everyone": everyone})
        return resp.json()  # type: ignore[no-any-return]

    async def unreserve(self, topic: str) -> dict[str, Any]:
        """DELETE /v1/account/reservation/{topic} — release a reservation."""
        resp = await self._request("DELETE", f"/v1/account/reservation/{topic}")
        return resp.json()  # type: ignore[no-any-return]

    # ------------------------------------------------------------------
    # Tokens
    # ------------------------------------------------------------------

    async def token_create(self, label: str | None = None, expires: int | None = None) -> dict[str, Any]:
        """POST /v1/account/token — create a new API token."""
        body: dict[str, Any] = {}
        if label:
            body["label"] = label
        if expires is not None:
            body["expires"] = expires
        resp = await self._request("POST", "/v1/account/token", json=body if body else None)
        return resp.json()  # type: ignore[no-any-return]

    async def token_extend(self, token: str, label: str | None = None, expires: int | None = None) -> dict[str, Any]:
        """PATCH /v1/account/token — extend or relabel a token."""
        body: dict[str, Any] = {"token": token}
        if label is not None:
            body["label"] = label
        if expires is not None:
            body["expires"] = expires
        resp = await self._request("PATCH", "/v1/account/token", json=body)
        return resp.json()  # type: ignore[no-any-return]

    async def token_revoke(self, token: str) -> dict[str, Any]:
        """DELETE /v1/account/token — revoke a token."""
        resp = await self._client.request(
            "DELETE",
            "/v1/account/token",
            headers={"X-Token": token},
        )
        if resp.status_code in (401, 403):
            raise AuthError(f"Token revocation failed ({resp.status_code})")
        if resp.status_code >= 400:
            raise NtfyError(f"Token revocation failed ({resp.status_code}): {resp.text[:200]}")
        return resp.json()  # type: ignore[no-any-return]
