# Claude Code specifics

## How Claude Code loads this repo

Option 1 — as a plugin (auto-discovered):

```bash
git clone https://github.com/upsidemax/upside-agent-skills.git ~/.claude/plugins/upside-agent-skills
```

Restart Claude Code. The five skills appear in `/skills` — invoke with `Skill(skill: "upside-test")` or by natural language matching the SKILL.md `description`.

Option 2 — as a workspace:

```bash
git clone https://github.com/upsidemax/upside-agent-skills.git
cd upside-agent-skills
claude
```

Claude will discover `skills/*/SKILL.md` files at session start and can route to them.

## Skill invocation semantics

Each `SKILL.md` is written to be **self-loading**: when its frontmatter matches, Claude reads the whole file, follows the "Main flow" section, and reaches for `references/*.md` only if a deeper detail is needed. The examples in `examples/` are also referenced from within each skill — Claude can `Bash python3 examples/01_register.py` directly.

## Preferred tool patterns

- Prefer `Bash` to run the Python examples over rewriting logic inline. The examples are already validated on QA.
- Use `Read` on reference files (like `signing.md`) rather than trying to derive the signing protocol from scratch.
- Use `Edit` on `examples/*.py` when the user asks for a variation (e.g., "buy ETH instead of BTC") — copy the file, tweak the constants, don't rewrite.

## Security posture

- All keys in `examples/*.py` are **generated at runtime** (`secrets.token_hex(32)`). Nothing is hard-coded.
- If a user asks Claude to save a key: warn them, then only save into a `.env` file that is `.gitignore`d.

## Common pitfalls

1. **Order accepted but doesn't appear in `userOrders`** — the contract has `priceReady: false`. Backend accepts the request (202) but the matching engine silently drops it. Tell the user to wait until `priceReady` is true, or use a different contract that's already ready.
2. **`auto-airdrop` doesn't fire** — usually just needs 10-30 seconds. If after 60s `depositNonce == 0` still, the simplest recovery is a fresh registration (a new wallet often lands the airdrop).
3. **Balance query returns null everywhere** — account and balance queries must use the `marketDeployerId` field.

## When in doubt

`skills/upside-advanced/references/error-codes.md` has the numeric-to-message table. That's usually the fastest way to explain a failure.
