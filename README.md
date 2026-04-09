# ntfy Blade MCP

Token-efficient MCP server for [ntfy](https://ntfy.sh) push notifications. Publish alerts, poll topics, manage tokens and reservations.

## Requirements

- Python 3.12+
- A ntfy server (self-hosted or ntfy.sh)
- Optional: bearer token for authenticated access

## Quick Start

```bash
# Install
uv sync

# Configure
export NTFY_BASE_URL=https://ntfy.sh
export NTFY_TOKEN=tk_your_token_here
export NTFY_DEFAULT_TOPIC=my-alerts
export NTFY_WRITE_ENABLED=true

# Run
uv run ntfy-blade-mcp
```

## Tools (10)

| Tool | Type | Description |
|------|------|-------------|
| `ntfy_info` | read | Server health + capabilities + stats (3-in-1) |
| `ntfy_account` | read | Usage limits, reserved topics, active tokens |
| `ntfy_poll` | read | Poll topic(s) for cached messages |
| `ntfy_publish` | write | Send notification (priority, tags, actions, markdown, delay) |
| `ntfy_cancel` | write | Cancel a scheduled message |
| `ntfy_reserve` | write | Reserve a topic (set ACL) |
| `ntfy_unreserve` | write | Release a topic reservation |
| `ntfy_token_create` | write | Create a new API token |
| `ntfy_token_extend` | write | Extend/relabel a token |
| `ntfy_token_revoke` | write | Revoke a token |

## Security Model

1. **Environment gate** — all write tools require `NTFY_WRITE_ENABLED=true`
2. **Per-call confirmation** — every write tool requires `confirm=true`
3. **Token redaction** — tokens are truncated in output (full token shown only on create)
4. **PII scrubbing** — bearer tokens and API keys redacted from error messages
5. **No admin endpoints** — user management excluded by design

## Token Efficiency

- `ntfy_info` collapses 3 API calls (health + config + stats) into 1 tool call
- Pipe-delimited output, null-field omission, truncation at 200 chars
- Default priority (3) omitted from poll output
- `NTFY_DEFAULT_TOPIC` eliminates per-call topic specification

## Environment Variables

| Variable | Required | Secret | Description |
|----------|----------|--------|-------------|
| `NTFY_BASE_URL` | yes | no | ntfy server URL |
| `NTFY_TOKEN` | no | yes | Bearer token (tk_...) |
| `NTFY_DEFAULT_TOPIC` | no | no | Default topic for publish/poll |
| `NTFY_WRITE_ENABLED` | no | no | Enable write operations |
| `TRANSPORT` | no | no | `stdio` (default) or `http` |
| `NTFY_MCP_PORT` | no | no | HTTP port (default: 8773) |
| `NTFY_MCP_API_TOKEN` | no | yes | HTTP transport bearer auth |

## Development

```bash
make install-dev   # Install with dev deps
make test          # Run unit tests
make check         # Lint + format + typecheck
make test-cov      # Tests with coverage
```

## Architecture

```
src/ntfy_blade_mcp/
├── __init__.py
├── __main__.py      # Entry point
├── server.py        # FastMCP + 10 @mcp.tool definitions
├── client.py        # httpx async client for ntfy API
├── formatters.py    # Pipe-delimited token-efficient output
└── models.py        # Config, gates, constants, exceptions
```

## Sidereal Marketplace

Contract: `notifications-push-v1` — see `sidereal-plugin.yaml`.

## Licence

MIT
