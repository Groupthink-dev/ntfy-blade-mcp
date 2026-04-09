"""ntfy Blade MCP server — 10 tools for push notification management.

Tools:
  READ:  ntfy_info, ntfy_account, ntfy_poll
  WRITE: ntfy_publish, ntfy_cancel
  TOPIC: ntfy_reserve, ntfy_unreserve
  TOKEN: ntfy_token_create, ntfy_token_extend, ntfy_token_revoke
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from ntfy_blade_mcp.client import NtfyClient
from ntfy_blade_mcp.formatters import (
    format_account,
    format_error,
    format_info,
    format_messages,
    format_publish_result,
    format_token,
)
from ntfy_blade_mcp.models import (
    MAX_ACTIONS,
    NtfyError,
    check_confirm_gate,
    check_write_gate,
    resolve_config,
    resolve_topic,
)

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "NtfyBlade",
    instructions=(
        "ntfy push notification operations. "
        "Publish notifications, poll topics, manage tokens and reservations. "
        "Write ops require NTFY_WRITE_ENABLED=true AND confirm=true."
    ),
)

# Lazy-initialised client (created on first tool call)
_client: NtfyClient | None = None
_config = resolve_config()


def _get_client() -> NtfyClient:
    global _client
    if _client is None:
        _client = NtfyClient(_config)
    return _client


# ============================================================================
# READ TOOLS
# ============================================================================


@mcp.tool()
async def ntfy_info() -> str:
    """Server health, capabilities, and message stats in one call."""
    try:
        client = _get_client()
        health, config, stats = await asyncio.gather(
            client.health(),
            client.config(),
            client.stats(),
        )
        return format_info(health, config, stats)
    except NtfyError as e:
        return format_error(e)


@mcp.tool()
async def ntfy_account() -> str:
    """Account info: usage limits, reserved topics, active tokens."""
    try:
        client = _get_client()
        data = await client.account()
        return format_account(data)
    except NtfyError as e:
        return format_error(e)


@mcp.tool()
async def ntfy_poll(
    topic: Annotated[str | None, Field(description="Topic to poll (default: NTFY_DEFAULT_TOPIC)")] = None,
    since: Annotated[
        str | None, Field(description="Fetch since: duration (10m), timestamp, message ID, or 'all'")
    ] = None,
    scheduled: Annotated[bool, Field(description="Include scheduled (not yet delivered) messages")] = False,
    priority: Annotated[str | None, Field(description="Filter by priority: comma-separated 1-5")] = None,
    tags: Annotated[str | None, Field(description="Filter by tags: comma-separated (AND logic)")] = None,
) -> str:
    """Poll a topic for cached messages. Returns newest first."""
    err, resolved = resolve_topic(topic, _config)
    if err:
        return err
    try:
        client = _get_client()
        messages = await client.poll(
            resolved,
            since=since,
            scheduled=scheduled,
            priority=priority,
            tags=tags,
        )
        return format_messages(messages, topic=resolved)
    except NtfyError as e:
        return format_error(e)


# ============================================================================
# WRITE TOOLS
# ============================================================================


@mcp.tool()
async def ntfy_publish(
    message: Annotated[str, Field(description="Notification body text")],
    topic: Annotated[str | None, Field(description="Target topic (default: NTFY_DEFAULT_TOPIC)")] = None,
    title: Annotated[str | None, Field(description="Notification title")] = None,
    priority: Annotated[int | None, Field(description="1=min 2=low 3=default 4=high 5=urgent", ge=1, le=5)] = None,
    tags: Annotated[list[str] | None, Field(description="Tags/emoji shortcodes, e.g. ['warning','skull']")] = None,
    click: Annotated[str | None, Field(description="URL opened when notification is tapped")] = None,
    icon: Annotated[str | None, Field(description="Notification icon URL")] = None,
    attach: Annotated[str | None, Field(description="External attachment URL")] = None,
    filename: Annotated[str | None, Field(description="Attachment filename")] = None,
    markdown: Annotated[bool, Field(description="Render message as markdown")] = False,
    delay: Annotated[str | None, Field(description="Schedule: '30m', '2h', 'tomorrow 3pm', unix timestamp")] = None,
    actions: Annotated[
        list[dict[str, Any]] | None, Field(description="Action buttons (max 3): {action, label, url}")
    ] = None,
    confirm: Annotated[bool, Field(description="Must be true — notifications cannot be retracted")] = False,
) -> str:
    """Publish a push notification via ntfy. Requires NTFY_WRITE_ENABLED=true AND confirm=true."""
    gate = check_write_gate(_config)
    if gate:
        return gate
    conf = check_confirm_gate(confirm, "Publishing a notification")
    if conf:
        return conf

    err, resolved = resolve_topic(topic, _config)
    if err:
        return err

    if actions and len(actions) > MAX_ACTIONS:
        return f"Error: Maximum {MAX_ACTIONS} actions per message."

    payload: dict[str, Any] = {"topic": resolved, "message": message}
    if title:
        payload["title"] = title
    if priority is not None:
        payload["priority"] = priority
    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click
    if icon:
        payload["icon"] = icon
    if attach:
        payload["attach"] = attach
    if filename:
        payload["filename"] = filename
    if markdown:
        payload["markdown"] = True
    if delay:
        payload["delay"] = delay
    if actions:
        payload["actions"] = actions

    try:
        client = _get_client()
        result = await client.publish(payload)
        return format_publish_result(result)
    except NtfyError as e:
        return format_error(e)


@mcp.tool()
async def ntfy_cancel(
    message_id: Annotated[str, Field(description="ID of the scheduled message to cancel")],
    topic: Annotated[str | None, Field(description="Topic (default: NTFY_DEFAULT_TOPIC)")] = None,
    confirm: Annotated[bool, Field(description="Must be true to cancel")] = False,
) -> str:
    """Cancel a scheduled (not yet delivered) message. Requires NTFY_WRITE_ENABLED=true AND confirm=true."""
    gate = check_write_gate(_config)
    if gate:
        return gate
    conf = check_confirm_gate(confirm, "Cancelling a scheduled message")
    if conf:
        return conf

    err, resolved = resolve_topic(topic, _config)
    if err:
        return err

    try:
        client = _get_client()
        await client.cancel(resolved, message_id)
        return f"Cancelled message {message_id} on {resolved}"
    except NtfyError as e:
        return format_error(e)


# ============================================================================
# TOPIC MANAGEMENT
# ============================================================================


@mcp.tool()
async def ntfy_reserve(
    topic: Annotated[str, Field(description="Topic name to reserve")],
    everyone: Annotated[
        str, Field(description="ACL for unauth users: deny-all, read-only, write-only, read-write")
    ] = "deny-all",
    confirm: Annotated[bool, Field(description="Must be true to reserve")] = False,
) -> str:
    """Reserve a topic (control access for unauthenticated users). Requires NTFY_WRITE_ENABLED=true AND confirm=true."""
    gate = check_write_gate(_config)
    if gate:
        return gate
    conf = check_confirm_gate(confirm, "Reserving a topic")
    if conf:
        return conf

    from ntfy_blade_mcp.models import validate_topic

    err = validate_topic(topic)
    if err:
        return err

    valid_acls = {"deny-all", "read-only", "write-only", "read-write"}
    if everyone not in valid_acls:
        return f"Error: Invalid ACL '{everyone}'. Must be one of: {', '.join(sorted(valid_acls))}"

    try:
        client = _get_client()
        await client.reserve(topic, everyone)
        return f"Reserved topic={topic} | everyone={everyone}"
    except NtfyError as e:
        return format_error(e)


@mcp.tool()
async def ntfy_unreserve(
    topic: Annotated[str, Field(description="Topic name to release")],
    confirm: Annotated[bool, Field(description="Must be true to release")] = False,
) -> str:
    """Release a topic reservation. Requires NTFY_WRITE_ENABLED=true AND confirm=true."""
    gate = check_write_gate(_config)
    if gate:
        return gate
    conf = check_confirm_gate(confirm, "Releasing a topic reservation")
    if conf:
        return conf

    from ntfy_blade_mcp.models import validate_topic

    err = validate_topic(topic)
    if err:
        return err

    try:
        client = _get_client()
        await client.unreserve(topic)
        return f"Released reservation on topic={topic}"
    except NtfyError as e:
        return format_error(e)


# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================


@mcp.tool()
async def ntfy_token_create(
    label: Annotated[str | None, Field(description="Human-readable label for the token")] = None,
    expires: Annotated[int | None, Field(description="Expiry as Unix epoch seconds (default: 72h from now)")] = None,
    confirm: Annotated[bool, Field(description="Must be true to create")] = False,
) -> str:
    """Create a new API token. Requires NTFY_WRITE_ENABLED=true AND confirm=true. Shows full token once."""
    gate = check_write_gate(_config)
    if gate:
        return gate
    conf = check_confirm_gate(confirm, "Creating an API token")
    if conf:
        return conf

    try:
        client = _get_client()
        result = await client.token_create(label=label, expires=expires)
        return format_token(result, show_full=True)
    except NtfyError as e:
        return format_error(e)


@mcp.tool()
async def ntfy_token_extend(
    token: Annotated[str, Field(description="Token string (tk_...)")],
    label: Annotated[str | None, Field(description="New label")] = None,
    expires: Annotated[int | None, Field(description="New expiry as Unix epoch seconds")] = None,
    confirm: Annotated[bool, Field(description="Must be true to extend")] = False,
) -> str:
    """Extend or relabel an existing token. Requires NTFY_WRITE_ENABLED=true AND confirm=true."""
    gate = check_write_gate(_config)
    if gate:
        return gate
    conf = check_confirm_gate(confirm, "Extending a token")
    if conf:
        return conf

    try:
        client = _get_client()
        result = await client.token_extend(token, label=label, expires=expires)
        return format_token(result)
    except NtfyError as e:
        return format_error(e)


@mcp.tool()
async def ntfy_token_revoke(
    token: Annotated[str, Field(description="Token string (tk_...) to revoke")],
    confirm: Annotated[bool, Field(description="Must be true to revoke")] = False,
) -> str:
    """Revoke (delete) an API token. Requires NTFY_WRITE_ENABLED=true AND confirm=true."""
    gate = check_write_gate(_config)
    if gate:
        return gate
    conf = check_confirm_gate(confirm, "Revoking a token")
    if conf:
        return conf

    try:
        client = _get_client()
        await client.token_revoke(token)
        return f"Revoked token {token[:12]}..."
    except NtfyError as e:
        return format_error(e)


# ============================================================================
# Entry point
# ============================================================================


def main() -> None:
    """Run the ntfy Blade MCP server."""
    from typing import Literal

    transport: Literal["stdio", "http", "sse", "streamable-http"] = "stdio"
    if _config.transport in ("http", "sse", "streamable-http"):
        transport = _config.transport  # type: ignore[assignment]
        mcp.run(transport=transport, host="127.0.0.1", port=_config.mcp_port)
    else:
        mcp.run(transport="stdio")
