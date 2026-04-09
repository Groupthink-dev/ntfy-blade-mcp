"""Configuration, write/confirm gates, constants, and exceptions for ntfy Blade MCP."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from enum import IntEnum

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASE_URL = "https://ntfy.sh"
DEFAULT_MCP_PORT = 8773
DEFAULT_POLL_LIMIT = 50
MAX_MESSAGE_BODY = 4096
MAX_ACTIONS = 3
TOPIC_PATTERN = re.compile(r"^[-_A-Za-z0-9]{1,64}$")


class Priority(IntEnum):
    """ntfy message priority levels."""

    MIN = 1
    LOW = 2
    DEFAULT = 3
    HIGH = 4
    URGENT = 5


PRIORITY_NAMES: dict[int, str] = {
    1: "min",
    2: "low",
    3: "default",
    4: "high",
    5: "urgent",
}

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class NtfyConfig:
    """Configuration resolved from environment variables."""

    base_url: str = field(default_factory=lambda: DEFAULT_BASE_URL)
    token: str | None = None
    default_topic: str | None = None
    write_enabled: bool = False
    mcp_port: int = DEFAULT_MCP_PORT
    mcp_api_token: str | None = None
    transport: str = "stdio"


def resolve_config() -> NtfyConfig:
    """Resolve configuration from environment variables."""
    return NtfyConfig(
        base_url=os.environ.get("NTFY_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        token=os.environ.get("NTFY_TOKEN"),
        default_topic=os.environ.get("NTFY_DEFAULT_TOPIC"),
        write_enabled=os.environ.get("NTFY_WRITE_ENABLED", "").lower() == "true",
        mcp_port=int(os.environ.get("NTFY_MCP_PORT", str(DEFAULT_MCP_PORT))),
        mcp_api_token=os.environ.get("NTFY_MCP_API_TOKEN"),
        transport=os.environ.get("TRANSPORT", "stdio").lower(),
    )


# ---------------------------------------------------------------------------
# Write gates
# ---------------------------------------------------------------------------


def check_write_gate(config: NtfyConfig) -> str | None:
    """Return an error string if writes are disabled, else None."""
    if not config.write_enabled:
        return "Error: Write operations disabled. Set NTFY_WRITE_ENABLED=true to enable."
    return None


def check_confirm_gate(confirm: bool, action: str) -> str | None:
    """Return an error string if confirm is not True, else None."""
    if not confirm:
        return (
            f"Error: {action} requires explicit confirmation. "
            "Set confirm=true to proceed. This is a safety gate — "
            "published notifications cannot be retracted."
        )
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_topic(topic: str) -> str | None:
    """Return an error string if the topic name is invalid, else None."""
    if not TOPIC_PATTERN.match(topic):
        return f"Error: Invalid topic '{topic}'. Must match [-_A-Za-z0-9]{{1,64}}."
    return None


def resolve_topic(topic: str | None, config: NtfyConfig) -> tuple[str | None, str]:
    """Resolve topic from argument or default config. Returns (error, topic)."""
    resolved = topic or config.default_topic
    if not resolved:
        return "Error: No topic specified and NTFY_DEFAULT_TOPIC not set.", ""
    err = validate_topic(resolved)
    if err:
        return err, ""
    return None, resolved


# ---------------------------------------------------------------------------
# PII scrubbing (error paths only)
# ---------------------------------------------------------------------------

_TOKEN_PATTERN = re.compile(r"tk_[A-Za-z0-9]{20,}")
_BEARER_PATTERN = re.compile(r"Bearer\s+\S+", re.IGNORECASE)


def scrub_pii(text: str) -> str:
    """Redact tokens and bearer strings from error messages."""
    text = _TOKEN_PATTERN.sub("[REDACTED_TOKEN]", text)
    text = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    return text


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class NtfyError(Exception):
    """Base exception. PII is scrubbed from string representation."""

    def __str__(self) -> str:
        return scrub_pii(super().__str__())


class AuthError(NtfyError):
    """Raised on 401/403 from the ntfy server."""

    pass


class ServerError(NtfyError):
    """Raised on 5xx from the ntfy server."""

    pass
