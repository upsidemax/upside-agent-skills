# Agent routing

This file tells any AI coding agent (Claude Code, Codex, Cursor, opencode, generic ChatGPT copy-paste) how to route user requests to the skills in this repo.

## Load order

At session start, load the five `SKILL.md` files (start with `upside-test` —
it's the guided entry point that runs whole flows in one command):

```
skills/upside-test/SKILL.md
skills/upside-onboarding/SKILL.md
skills/upside-trading/SKILL.md
skills/upside-websocket/SKILL.md
skills/upside-advanced/SKILL.md
```

Each has a YAML frontmatter `description` field that lists the trigger phrases. Route the user's request to the skill whose description best matches.

## Routing table (fast path)

| user says … | route to |
|---|---|
| "try it" / "let me experience it" / "demo" / "just show me" / "体验" / "试用" / "我想试试" | `upside-test` (runs a full guided flow) |
| "create an account" / "sign me up" / "register" / "I want to trade but have no account" | `upside-onboarding` |
| "buy X" / "sell Y" / "place a limit order" / "cancel my order" / "check my orders" / "what's the BTC price" | `upside-trading` |
| "stream fills" / "subscribe to trades" / "watch the order book" / "listen to my order updates" | `upside-websocket` |
| "give my bot permission to trade" / "TP/SL" / "stop loss" / "what does errorCode 30 mean" | `upside-advanced` |

If the request spans multiple skills, run onboarding first (it's the prerequisite) and then the target skill.

## Preflight

Before any action, verify:

1. **Deps installed** — `pip show eth-keys eth-utils requests websocket-client` should all return a version.
2. **QA reachable** — `curl -s -m 5 -X POST https://dev.upsidemax.xyz/info -H 'Content-Type: application/json' -d '{"type":"marketState","asset":"1"}'` should return JSON with `type: "marketState"`. If not, retry shortly; if it persists, contact the Upside team.
3. **User has a private key** — if not, `examples/01_register.py` generates one. Never accept a private key over chat; ask the user to run the script themselves.

## Prohibited

- **Never** use mainnet keys with these skills. QA only.
- **Never** paste user private keys into responses or logs.
- **Never** guess field names — account and balance queries use `marketDeployerId`.

## Handling stale info

If a call unexpectedly returns `unsupported info type` or `missing/invalid <fieldName>`, the backend probably renamed a field. Do NOT retry aggressively; instead:

1. `curl` the URL directly and dump the full response body.
2. Check [`skills/upside-advanced/references/error-codes.md`](skills/upside-advanced/references/error-codes.md) for the latest known field names.
3. If still stuck, ask the user to re-verify against the latest API doc.
