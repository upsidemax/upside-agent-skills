# Upside Agent Skills

AI agent skills for Upside, a decentralized, self-custody perpetual-futures exchange. The skills let an AI coding assistant register, trade, and stream over Upside's REST and WebSocket APIs — on **Mainnet** by default, or on Devnet.

Each skill is a single Markdown file (`SKILL.md`) with a YAML frontmatter header. An AI agent can read the frontmatter to know *when* to activate a skill and *how* to complete a task, without needing the user to describe the flow.

## What you get

- **5 skills** — a guided **`upside-test`** to try the whole product in one command, plus four covering the full trading lifecycle from zero to your first order.
- **10 runnable Python scripts** in [`examples/`](examples/) — copy, paste, run.
- **No CLI dependency** — everything is raw HTTP / WebSocket.

## Skills

| skill | when to activate | main flow |
|---|---|---|
| [`upside-test`](skills/upside-test/SKILL.md) | user wants to **try / experience** the product ("let me try it", "体验") | one-command flows: register → balance → place & cancel an order, plus live market, explain, tour |
| [`upside-onboarding`](skills/upside-onboarding/SKILL.md) | user has no account, or funds are 0 | register (needs an invitation code) → check balance → fund the account if it is 0 |
| [`upside-trading`](skills/upside-trading/SKILL.md) | user wants to trade, query price, or manage orders | market state → place limit/IOC → query orders → cancel |
| [`upside-websocket`](skills/upside-websocket/SKILL.md) | user wants live price / fills / order updates | JSON `{method:"subscribe"}` on `l2Book / bbo / trades / config / orderUpdates` |
| [`upside-advanced`](skills/upside-advanced/SKILL.md) | user asks about bots, TP/SL, or hits a numeric error code | agent delegation (approveAgent), TP/SL entries, full errorCode table |

## Quick start

```bash
# No git required — download + extract the archive:
curl -L https://github.com/upsidemax/upside-agent-skills/archive/refs/heads/main.tar.gz | tar xz
cd upside-agent-skills-main
# (or, if you have git:  git clone https://github.com/upsidemax/upside-agent-skills.git && cd upside-agent-skills)

./install.sh                             # installs the Python dependencies
export UPSIDE_INVITE_CODE=<your-code>    # request one from the Upside team
python3 examples/quick_start.py          # e2e on Mainnet: register → check balance → place & cancel an order
```

> Only **Python 3.9+** is required. `curl`/`tar` (for the download) ship with macOS, Linux, and Windows 10+; `git` is optional.

New to DEX or Upside? Read **[docs/getting-started.md](docs/getting-started.md)** first — 10-minute guided walkthrough with all the concepts (mo=0 vs MO=1, signer model, EIP-712 signing). Chinese: **[getting-started.zh-CN.md](docs/getting-started.zh-CN.md)**.

Hit an error? Check **[docs/faq.md](docs/faq.md)** — every failure mode from the skill references, one page. Chinese: **[faq.zh-CN.md](docs/faq.zh-CN.md)**.

Prefer curl over Python? See **[docs/curl-cookbook.md](docs/curl-cookbook.md)** — every action in pure shell + a tiny inline Python signer.

Want to save your key across script runs?
`01_register.py` and `quick_start.py` save `USER_PRIVATE_KEY` / `USER_ACCOUNT_ID`
to the gitignored `.env` for you (the key is never printed). Later scripts pick it up:
```bash
python3 examples/10_use_saved_wallet.py   # picks up .env automatically
```

A newly registered account has a **zero balance** — fund it before trading
(contact the Upside team for how).

## Environments

| env | REST base | WS base | EIP-712 chainId | invitation code required? |
|---|---|---|---|---|
| **Mainnet (default)** | `https://upsidemax.xyz` | `wss://upsidemax.xyz/ws` | `9788` | yes |
| Devnet | `https://dev.upsidemax.xyz` | `wss://dev.upsidemax.xyz/ws` | `9767` | yes |

> Set your invitation code with `export UPSIDE_INVITE_CODE=<your-code>` before registering (request one from the Upside team). To use Devnet, `export UPSIDE_BASE_URL=https://dev.upsidemax.xyz`; the WebSocket URL and chain ID follow it. Mainnet is real funds — see [SECURITY.md](SECURITY.md).

## Three common mistakes to avoid

1. **`inviteCode` goes at the envelope level, not inside `action`.** Placing it in `action` returns `inviteCode required`. See [signing.md](skills/upside-onboarding/_shared/signing.md).
2. **Balance queries use `marketDeployerId`.** Use this field name for account and balance queries. See [query-account.md](skills/upside-onboarding/references/query-account.md).
3. **The WebSocket uses a JSON subscribe protocol.** Subscribe with `{method:"subscribe", subscription:{type,asset}}`. See [websocket-protocol.md](skills/upside-websocket/references/websocket-protocol.md).

## Skill loading

- **Claude Code**: skills auto-load if this repo is cloned into `~/.claude/plugins/` or referenced via [`.claude-plugin/plugin.json`](.claude-plugin/plugin.json).
- **Codex / Cursor / opencode**: see [`AGENTS.md`](AGENTS.md).
- **Any other agent**: just read [`skills/*/SKILL.md`](skills/) files directly. Frontmatter tells you when to activate.

## Repo layout

```
.
├── README.md            # this file
├── AGENTS.md            # multi-agent routing
├── CLAUDE.md            # Claude Code specifics
├── SECURITY.md          # key-safety notes
├── install.sh           # one-shot dep install
├── .env.example         # copy to .env to persist your key across runs
├── docs/                # human-readable guides
│   ├── getting-started.md          # 10-min guided tour (English)
│   ├── getting-started.zh-CN.md    # 中文快速上手
│   ├── faq.md                      # error decoder (English)
│   ├── faq.zh-CN.md                # 常见问题（中文）
│   └── curl-cookbook.md            # pure-shell recipes
├── examples/            # runnable Python scripts
│   ├── common.py            # shared helpers (signing, HTTP, .env loader)
│   ├── quick_start.py       # one-shot e2e
│   └── 01_register.py … 10_use_saved_wallet.py
└── skills/              # AI-agent skill files (Claude / Codex / Cursor)
    ├── upside-test/     # guided one-command experience (start here)
    ├── upside-onboarding/
    ├── upside-trading/
    ├── upside-websocket/
    └── upside-advanced/
```

## License

MIT — see [`LICENSE`](LICENSE).

## Contributing

Field names, error codes, and channel semantics can change as the backend evolves. If a skill file drifts from reality, file an issue or a PR with the actual response you observed. All references include a "last verified" date.
