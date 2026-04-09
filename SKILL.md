---
name: ntfy-push-notifications
description: >
  Manages ntfy push notifications — publish alerts, poll topics, manage tokens and reservations.
  Use when user mentions 'notify', 'ntfy', 'push notification', 'alert', 'send notification'.
---

# ntfy Blade MCP — Skill Guide

## Token Efficiency Rules (MANDATORY)

1. **Use `ntfy_info` first** to verify connectivity — it collapses 3 API calls into 1
2. **Set `NTFY_DEFAULT_TOPIC`** so most `ntfy_publish` calls skip the topic parameter
3. **Never poll without `since`** — use `since=10m` or a message ID to avoid fetching entire history
4. **All writes need both gates** — `NTFY_WRITE_ENABLED=true` env var AND `confirm=true` per call

## Quick Start

### Send a notification
```
ntfy_publish(message="Deploy complete", title="CI/CD", priority=4, tags=["white_check_mark"], confirm=true)
```

### Poll for recent messages
```
ntfy_poll(since="30m")
```

### Check server health
```
ntfy_info()
```

### Schedule a delayed notification
```
ntfy_publish(message="Reminder: standup", delay="tomorrow 9am", confirm=true)
```

### Send with action buttons
```
ntfy_publish(
  message="PR #42 ready for review",
  actions=[{"action": "view", "label": "Open PR", "url": "https://github.com/org/repo/pull/42"}],
  confirm=true
)
```

## Workflows

### Alert pipeline
1. `ntfy_info()` — verify server is healthy
2. `ntfy_publish(message=..., priority=5, tags=["rotating_light"], confirm=true)` — send urgent alert
3. `ntfy_poll(since="1m")` — verify it appears in cache

### Token rotation
1. `ntfy_account()` — list current tokens
2. `ntfy_token_create(label="new-automation", confirm=true)` — create replacement
3. Update env var with new token
4. `ntfy_token_revoke(token="tk_old...", confirm=true)` — revoke old token

### Topic access control
1. `ntfy_reserve(topic="private-alerts", everyone="deny-all", confirm=true)` — lock down topic
2. Only authenticated users with your token can publish/subscribe

## Natural Language Mapping

| User says | Tool |
|-----------|------|
| "send a notification" | `ntfy_publish` |
| "check for new alerts" | `ntfy_poll` |
| "is ntfy working?" | `ntfy_info` |
| "what are my limits?" | `ntfy_account` |
| "cancel that scheduled message" | `ntfy_cancel` |
| "lock down that topic" | `ntfy_reserve` |
| "create a new token" | `ntfy_token_create` |

## Priority Reference

| Value | Name | Behaviour |
|-------|------|-----------|
| 1 | min | Silent, folded |
| 2 | low | No sound |
| 3 | default | Standard |
| 4 | high | Pop-over |
| 5 | urgent | Pop-over + vibration |
