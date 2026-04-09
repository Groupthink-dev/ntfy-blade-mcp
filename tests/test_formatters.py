"""Tests for token-efficient formatters."""

from __future__ import annotations

from ntfy_blade_mcp.formatters import (
    format_account,
    format_info,
    format_message,
    format_messages,
    format_publish_result,
    format_token,
    truncate,
)


class TestTruncate:
    def test_short_text(self) -> None:
        assert truncate("hello", 10) == "hello"

    def test_exact_length(self) -> None:
        assert truncate("hello", 5) == "hello"

    def test_long_text(self) -> None:
        result = truncate("a" * 20, 10)
        assert len(result) == 10
        assert result.endswith("...")

    def test_empty(self) -> None:
        assert truncate("") == ""

    def test_none(self) -> None:
        assert truncate(None) == ""  # type: ignore[arg-type]


class TestFormatInfo:
    def test_healthy(self) -> None:
        result = format_info(
            {"healthy": True},
            {"base_url": "https://ntfy.sh", "enable_signup": True, "enable_reservations": True},
            {"messages": 5000, "messages_rate": 2.5},
        )
        assert "healthy=yes" in result
        assert "msgs=5000" in result
        assert "rate=2.5/s" in result
        assert "signup" in result

    def test_unhealthy(self) -> None:
        result = format_info({"healthy": False}, {}, {})
        assert "healthy=NO" in result


class TestFormatAccount:
    def test_full(self) -> None:
        data = {
            "username": "piers",
            "role": "admin",
            "tier": {"name": "Pro"},
            "stats": {"messages": 100, "messages_remaining": 4900, "emails": 2, "emails_remaining": 18},
            "reservations": [{"topic": "alerts", "everyone": "deny-all"}],
            "tokens": [{"token": "tk_12345678901234567890", "label": "automation"}],
        }
        result = format_account(data)
        assert "user=piers" in result
        assert "tier=Pro" in result
        assert "messages=100/5000" in result
        assert "alerts(deny-all)" in result
        assert "automation" in result

    def test_anonymous(self) -> None:
        result = format_account({})
        assert "user=anonymous" in result


class TestFormatMessage:
    def test_basic(self) -> None:
        msg = {"id": "abc123", "time": 1700000000, "message": "Hello world"}
        result = format_message(msg)
        assert "abc123" in result
        assert "Hello world" in result

    def test_high_priority(self) -> None:
        msg = {"id": "x", "priority": 5, "message": "urgent"}
        result = format_message(msg)
        assert "P5(urgent)" in result

    def test_default_priority_omitted(self) -> None:
        msg = {"id": "x", "priority": 3, "message": "normal"}
        result = format_message(msg)
        assert "P3" not in result

    def test_with_tags_and_title(self) -> None:
        msg = {"id": "x", "tags": ["warning", "skull"], "title": "Alert!", "message": "fire"}
        result = format_message(msg)
        assert "warning,skull" in result
        assert "[Alert!]" in result

    def test_attachment_fallback(self) -> None:
        msg = {"id": "x", "attachment": {"name": "report.pdf"}}
        result = format_message(msg)
        assert "[attachment: report.pdf]" in result


class TestFormatMessages:
    def test_empty(self) -> None:
        result = format_messages([], topic="test")
        assert "no messages" in result
        assert "test" in result

    def test_with_messages(self) -> None:
        msgs = [
            {"id": "a", "time": 1, "message": "first"},
            {"id": "b", "time": 2, "message": "second"},
        ]
        result = format_messages(msgs, topic="alerts")
        assert "2 message(s)" in result
        assert "first" in result
        assert "second" in result


class TestFormatPublishResult:
    def test_full(self) -> None:
        result = format_publish_result({"id": "hwQ2YpKdmg", "topic": "alerts", "expires": 1673542291})
        assert "id=hwQ2YpKdmg" in result
        assert "topic=alerts" in result
        assert "expires=1673542291" in result

    def test_empty(self) -> None:
        assert format_publish_result({}) == "published"


class TestFormatToken:
    def test_full_shown_on_create(self) -> None:
        result = format_token({"token": "tk_AbCdEfGh1234567890ab", "label": "test", "expires": 999}, show_full=True)
        assert "tk_AbCdEfGh1234567890ab" in result
        assert "label=test" in result

    def test_truncated_by_default(self) -> None:
        result = format_token({"token": "tk_AbCdEfGh1234567890ab"})
        assert "tk_AbCdEfGh1..." in result
        assert "567890ab" not in result
