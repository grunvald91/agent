# Universal Agent Runtime — independent of Claude

A small **executable Python 3.11+ reference implementation**, combining the run-loop idea in [Anthropic's agents example](https://github.com/anthropics/claude-quickstarts/tree/main/agents) with the safety principles in [Building effective agent automations](https://claude.dev/blog/building-effective-agent-automations/). **Not** a copy of Anthropic's SDK. Zero third-party dependencies; no required Claude account, GitHub Actions or always-on Codespaces.

## Implemented now

- Sources: offline JSON fixture; GitHub Issues/PRs with pagination, 5-minute boundary overlap and `updated_at` bookmarks per repository.
- Destination: local JSONL outbox or Telegram Bot API with delivery acknowledgement. Telegram does **not** offer automatic outbound-message lookup. Ambiguous delivery blocks further sends pending operator review.
- Durable SQLite: cursors, report ledger, run history, atomic finalization and single-worker lock.
- Re-check each selected event before publication; ignore resolved issues; report unavailable sources explicitly; do not advance their checkpoints.
- Optional **OpenAI-compatible chat-completions** model adapter. Endpoints/models configured through JSON and environment. Supported *if* the selected provider actually exposes compatible API; native Claude APIs and MCP tools are **not** implemented in this MVP. Deterministic reports run without any model.
- Estimate a per-call model spending ceiling from configured token prices and `max_tokens`; actual provider invoicing and absolute caps require enforcement at the provider too. Maximum number of events is hard-limited.
- External scheduling by systemd timer (sample provided); `Persistent=true` requests catch-up after missed scheduled runs. Python runtime itself does not create a cloud scheduler.

## Try completely offline (no API keys)

```bash
cp config.example.json config.json
python3 agent_runtime.py dry-run --config config.json
python3 -m unittest discover -s tests -v
python3 agent_runtime.py run --config config.json
python3 agent_runtime.py status --config config.json
```

`dry-run` previews without writing bookmarks, ledger, run records or sending notifications. `run` sends to the local JSONL outbox configured in `config.json`; run twice to confirm it doesn't resend the same version. `config.json`, SQLite and output logs are excluded by `.gitignore`.

## Enable GitHub as a source

In `config.json`, replace `sources` with:

```json
"sources": [{"type":"github_issues", "repo":"grunvald91/agent"}]
```

Set **read-only** `GITHUB_TOKEN` in the worker environment. Do not commit secrets. Run `dry-run` before a real send. First scan can be large; if capped, it fails closed (no bookmark advance). GitHub's Issues API also returns pull requests, which appear in this example as issue-like events. This worker is **not** a GitHub code-writing agent.

## Enable Telegram

Use `"destination": {"type":"telegram", "chat_id":"YOUR_CHAT_ID"}` and securely set `TELEGRAM_BOT_TOKEN`. Test with a separate chat before production. Sending requires an authorized bot; no messages are sent by `dry-run`. The real `run` sends without an interactive approval, so treat the configuration as explicit authorization.

If the request might have succeeded but confirmation was lost, status becomes `maybe_posted`. The next run is blocked, not retried automatically. Inspect Telegram manually and, **only if delivery is confirmed**, run:

```bash
python3 agent_runtime.py reconcile --config config.json --message-id VERIFIED_MESSAGE_ID
```

For a local file destination, `reconcile` can automatically match the unique run ID in the outbox. If delivery **was not** confirmed, investigate and recover manually before allowing retry; do not guess. If the process crashed, the SQLite mutex remains locked. After checking that **no worker is running**:

```bash
python3 agent_runtime.py reset-lock --config config.json --confirm-no-worker
python3 agent_runtime.py reconcile --config config.json
```

The reconciliation check applies to unknown **delivery**, not lost read operations. Never use `--message-id` without actual receiver confirmation; that would cause lost events.

## Optional model provider (OpenAI-compatible HTTP)

Add to `config.json`:

```json
"model": {
  "type": "openai_compatible",
  "base_url": "https://YOUR_PROVIDER/v1",
  "model": "MODEL_ID",
  "key_env": "MODEL_API_KEY",
  "max_output_tokens": 250,
  "max_run_usd": 0.05,
  "usd_per_million_input_tokens": 0.5,
  "usd_per_million_output_tokens": 2.0
}
```

Those are **illustrative rates**, not claims of current provider pricing. Replace with actual prices and compatible endpoint. Put the key into `MODEL_API_KEY` environment securely. The model writes only prose; event collection, verified links, budgets and memory remain under program control. A provider might reject OpenAI-compatible semantics or use different token-accounting; test compatibility and verify invoices. An LLM output can still be wrong; don't use this demo for unattended consequential decisions.

## Scheduling (not enabled by default)

Edit `deploy/agent.service` (`User`, `WorkingDirectory`, Python path and configuration path), install it as a **systemd** unit together with `deploy/agent.timer` and check using systemd tooling:

```bash
sudo cp deploy/agent.service deploy/agent.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start agent.service       # one real test send, after configuration
sudo systemctl status agent.service
sudo systemctl enable --now agent.timer # deliberate authorization for recurring runs
sudo systemctl list-timers agent.timer
```

Timer example: **daily at 09:00 Europe/Moscow**; edit it before enabling. `Persistent=true` handles missed timer activations on systems that support this systemd feature. Missed source events are recovered from saved bookmarks, not a fixed 24-hour window. No systemd/SSH deployment is performed by this repository.

## Operator checklist / limitations

- Permissions: GitHub read only, Telegram post only, secret env variables secured; external data are **never** treated as system commands.
- Check `status`, unit logs, stale cursors, and test alerting for missed runs. This demo does **not** include external uptime alerting, server-side credential rotation, multi-instance distributed locks, deployment, an MCP gateway, a real tool-calling planner, or an approval UI.
- Process crashes can leave a lock that needs inspection; this fail-closed design prevents silent duplicates. SQLite assumes a single host and local persistent disk. Use a proper transactional shared DB and distributed lock before scaling horizontally.
- Telegram can fail on long reports; check provider message length and error behavior.
- No Actions CI jobs are configured. Test locally or by your normal Codex environment.

## Layout

`agent_runtime.py` — runnable worker, storage and adapters.

`config.example.json` and `examples/events.json` — offline starting point.

`tests/test_runtime.py` — safety and reliability checks.

`deploy/agent.service`, `deploy/agent.timer` — **disabled** scheduling templates.

`.agents/skills/effective-agent-automations/SKILL.md` and `.claude/skills/.../SKILL.md` — skill documentation for Codex and Claude Code.
