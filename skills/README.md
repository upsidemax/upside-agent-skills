# Skills index

Each subdirectory is one skill: `SKILL.md` is the main entry with frontmatter; `references/` and `_shared/` hold deeper docs the skill can lazily load.

| skill | when it fires |
|---|---|
| [upside-test](upside-test/SKILL.md) | user wants to **try / experience** the product in one command (entry skill) |
| [upside-onboarding](upside-onboarding/SKILL.md) | user has no account or 0 balance |
| [upside-trading](upside-trading/SKILL.md) | user wants prices, orders, or cancels |
| [upside-websocket](upside-websocket/SKILL.md) | user wants a live stream |
| [upside-advanced](upside-advanced/SKILL.md) | agent bots, TP/SL, or a numeric error the user can't decode |

## Common shared references

Referenced by more than one skill:

- [`upside-onboarding/_shared/signing.md`](upside-onboarding/_shared/signing.md) — EIP-712 envelope format
- [`upside-onboarding/_shared/endpoints.md`](upside-onboarding/_shared/endpoints.md) — QA URLs, WS URL
- [`upside-onboarding/_shared/preflight.md`](upside-onboarding/_shared/preflight.md) — env checks

## Skill file format

Each `SKILL.md` starts with YAML frontmatter:

```yaml
---
name: <kebab-case-id>
description: "<one sentence including trigger phrases>"
license: MIT
metadata:
  version: "0.1.0"
---
```

The rest is Markdown Claude/agent reads top-to-bottom.
