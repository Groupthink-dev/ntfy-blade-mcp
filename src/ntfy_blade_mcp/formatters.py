"""Token-efficient output formatters for ntfy Blade MCP.

All formatters return compact pipe-delimited strings optimised for LLM consumption.
Null fields are omitted. Long message text is truncated.
"""

from __future__ import annotations

from typing import Any

from ntfy_blade_mcp.models import PRIORITY_NAMES

_MAX_MSG_LEN = 200


def truncate(text: str, max_len: int = _MAX_MSG_LEN) -> str:
    """Truncate with ellipsis if exceeding max_len."""
    if not text or len(text) <= max_len:
        return text or ""
    return text[: max_len - 3] + "..."


def _safe(value: Any) -> str:
    """Stringify, empty for None."""
    return str(value) if value is not None else ""


# ---------------------------------------------------------------------------
# Server info (collapsed from health + config + stats)
# ---------------------------------------------------------------------------


def format_info(health: dict[str, Any], config: dict[str, Any], stats: dict[str, Any]) -> str:
    """Collapse health, config, and stats into a single compact response."""
    parts: list[str] = []

    # Health
    healthy = health.get("healthy", False)
    parts.append(f"healthy={'yes' if healthy else 'NO'}")

    # Stats
    total = stats.get("messages", 0)
    rate = stats.get("messages_rate", 0.0)
    if total:
        parts.append(f"msgs={total}")
    if rate:
        parts.append(f"rate={rate:.1f}/s")

    # Capabilities (only non-default flags)
    flags: list[str] = []
    for key in ("enable_signup", "enable_reservations", "enable_web_push", "enable_calls", "enable_emails"):
        val = config.get(key)
        if val is True:
            short = key.replace("enable_", "")
            flags.append(short)
    if flags:
        parts.append(f"caps={','.join(flags)}")

    base = config.get("base_url", "")
    if base:
        parts.append(f"url={base}")

    require_login = config.get("require_login", False)
    if require_login:
        parts.append("auth=required")

    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------


def format_account(data: dict[str, Any]) -> str:
    """Format account info: limits, usage, reservations, tokens."""
    lines: list[str] = []

    # Identity
    username = data.get("username", "anonymous")
    role = data.get("role", "user")
    tier = data.get("tier", {})
    tier_name = tier.get("name", "") if isinstance(tier, dict) else str(tier)
    identity = f"user={username} | role={role}"
    if tier_name:
        identity += f" | tier={tier_name}"
    lines.append(identity)

    # Usage vs limits
    s = data.get("stats", {})
    if s:
        usage_parts: list[str] = []
        for key in ("messages", "emails", "calls"):
            used = s.get(key, 0)
            remaining = s.get(f"{key}_remaining")
            if used or remaining:
                label = f"{key}={used}"
                if remaining is not None:
                    label += f"/{used + remaining}"
                usage_parts.append(label)
        if usage_parts:
            lines.append("usage: " + " | ".join(usage_parts))

    # Reservations
    reservations = data.get("reservations", [])
    if reservations:
        res_parts = [f"{r.get('topic', '?')}({r.get('everyone', '?')})" for r in reservations]
        lines.append(f"topics: {', '.join(res_parts)}")

    # Tokens (redacted)
    tokens = data.get("tokens", [])
    if tokens:
        tok_parts: list[str] = []
        for t in tokens:
            label = t.get("label") or t.get("token", "")[:8] + "..."
            tok_parts.append(label)
        lines.append(f"tokens: {', '.join(tok_parts)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Messages (poll results)
# ---------------------------------------------------------------------------


def format_message(msg: dict[str, Any]) -> str:
    """Format a single polled message.

    Format: id | time | P{priority} | tags | title | message
    """
    parts: list[str] = [msg.get("id", "?")]

    time_val = msg.get("time")
    if time_val:
        parts.append(str(time_val))

    priority = msg.get("priority", 3)
    if priority != 3:
        name = PRIORITY_NAMES.get(priority, str(priority))
        parts.append(f"P{priority}({name})")

    tags = msg.get("tags")
    if tags:
        parts.append(",".join(tags))

    title = msg.get("title")
    if title:
        parts.append(f"[{truncate(title, 60)}]")

    message = truncate(msg.get("message", ""))
    if message:
        parts.append(message)
    elif msg.get("attachment"):
        att = msg["attachment"]
        parts.append(f"[attachment: {att.get('name', 'file')}]")

    return " | ".join(parts)


def format_messages(messages: list[dict[str, Any]], topic: str | None = None) -> str:
    """Format a list of polled messages."""
    if not messages:
        return f"(no messages{f' on {topic}' if topic else ''})"
    header = f"{len(messages)} message(s)"
    if topic:
        header += f" on {topic}"
    lines = [header]
    lines.extend(format_message(m) for m in messages)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Publish confirmation
# ---------------------------------------------------------------------------


def format_publish_result(result: dict[str, Any]) -> str:
    """Format a publish confirmation.

    Format: id=X | topic=Y | expires=Z
    """
    parts: list[str] = []
    msg_id = result.get("id")
    if msg_id:
        parts.append(f"id={msg_id}")

    topic = result.get("topic")
    if topic:
        parts.append(f"topic={topic}")

    expires = result.get("expires")
    if expires:
        parts.append(f"expires={expires}")

    event = result.get("event")
    if event and event != "message":
        parts.append(f"event={event}")

    return " | ".join(parts) if parts else "published"


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------


def format_token(token_data: dict[str, Any], *, show_full: bool = False) -> str:
    """Format a token response.

    Format: token=tk_...[:8] | label=X | expires=Y
    """
    parts: list[str] = []
    tok = token_data.get("token", "")
    if tok:
        display = tok if show_full else tok[:12] + "..."
        parts.append(f"token={display}")

    label = token_data.get("label")
    if label:
        parts.append(f"label={label}")

    expires = token_data.get("expires")
    if expires:
        parts.append(f"expires={expires}")

    last_access = token_data.get("last_access")
    if last_access:
        parts.append(f"last_access={last_access}")

    return " | ".join(parts) if parts else "ok"


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


def format_error(error: Exception) -> str:
    """Format an error for tool output."""
    return f"Error: {error}"
