---
name: upside-test
description: "UpsideMAX guided experience — the ONE entry skill that lets a user try the product end-to-end in single commands, no setup. When it fires, show the flow menu, then run one wrapped flow per request with sensible defaults (don't interrogate the user for parameters). Trigger when the user says: try it / let me try / demo / show me / walk me through / experience / play with / give it a go / quick demo / one-click / take me through / I just want to see it work / can I test / 体验 / 试用 / 试一下 / 演示 / 走一遍 / 带我用一下 / 快速体验 / 一键体验 / 我想试试 / 直接跑一下 / 能演示吗. Wraps register, balance, order, positions, orders, cancel, and live WebSocket into single commands (Devnet by default, Mainnet optional); routes to upside-onboarding / upside-trading / upside-websocket / upside-advanced for depth."
license: MIT
metadata:
  author: upside-agent-skills
  version: "0.1.0"
  homepage: "https://dev.upsidemax.xyz"
  agent:
    requires:
      python: ">=3.9"
      packages: ["eth-account", "eth-keys", "eth-utils", "eth-hash[pycryptodome]", "requests", "websocket-client"]
    install:
      - id: pip
        kind: python
        packages: ["eth-account", "eth-keys", "eth-utils", "eth-hash[pycryptodome]", "requests", "websocket-client"]
        label: "Install Python dependencies"
---

# UpsideMAX — Test Drive

The fastest way to **experience UpsideMAX**. Every flow is one command that runs
end-to-end and prints a friendly summary. The test drive runs on **Devnet**
(`https://dev.upsidemax.xyz`, chainId 9767) by default. Set
`UPSIDE_BASE_URL=https://upsidemax.xyz` to run it on Mainnet (real funds) instead —
the other skills and the `examples/` scripts default to Mainnet. No private keys
are pasted into chat — wallets are generated locally and kept in a per-environment
session file (`~/.upside_test.<host>.json`, mode 600) so flows chain together.

All flows are a single launcher script. **Always invoke it by absolute path** so it
runs from any working directory:

```bash
# Installed as a Claude Code plugin (CLAUDE_PLUGIN_ROOT is set for you):
python3 "${CLAUDE_PLUGIN_ROOT}/skills/upside-test/scripts/play.py" <command>

# Or from a cloned repo / Codex workspace, run from the repo root:
python3 skills/upside-test/scripts/play.py <command>
```

Dependencies self-install on first run. Examples below write `play.py <command>` for
brevity — expand it to the absolute path above.

## How to drive this skill (keep it frictionless)

1. **On invocation, just run `menu` and show its numbered list.** Do **not** run
   any preamble: no dependency probing (`import …`), no connectivity `curl` — the
   launcher self-installs deps and reports network errors on its own. The menu is
   **numbered** and shows the environment; the user replies with a **number** (e.g.
   `3`) or a flow name — run that flow by passing the number (`play.py 3`) or the
   name (`play.py status`). **After every flow finishes, run `menu` again and show
   the numbered list** so the user always picks the next action by number — keep
   every turn menu-driven. **Shortcut:** if the user already said "try it" /
   "让我体验" / "我想试试", skip the menu and run `full` directly (account → balance →
   a resting limit order placed and cancelled) — but first apply the invitation
   code rule in step 2 if it will register.
2. **Registration needs an invitation code — ask for it first.** Any flow that would
   **register a new account** (`register`, or `full` / `order` / `positions` when
   there is **no** saved session yet) requires an invitation code, on Mainnet and
   Devnet. **Before running it, if the user hasn't already given you one, STOP and
   ask them to enter their invitation code** (they get one from the UpsideMAX team);
   wait for their reply. Then run the flow with the code prefixed:
   `UPSIDE_INVITE_CODE=<their-code> python3 "${CLAUDE_PLUGIN_ROOT}/skills/upside-test/scripts/play.py" <flow>`.
   Never register without a code the user gave you. (If a session already exists,
   flows reuse it — no code needed, so don't ask.)
3. **A new account has a zero balance.** After registering, the launcher checks the
   balance once and, if it is zero, stops: on Devnet the user contacts the UpsideMAX
   team for Devnet funds; on Mainnet the user deposits funds into the account.
   Relay that and stop — do not retry, poll, or re-register.
4. **Run one command per request, with defaults.** Do **not** interrogate the
   user for price/size/contract. Only pass `--flags` if they explicitly ask to
   customize (e.g. "sell instead of buy", "size 5"). On Mainnet, never place an
   order the user did not ask for.
5. **Match the user's language.** Pass `--lang zh` when the user writes Chinese
   (or set `UPSIDE_LANG=zh`) so the script prints natively; otherwise relay its
   plain-language output and its `→ Next:` hint in the user's language. The output
   is friendly by design (`✓ Order placed…`, `🎯 It filled…`) — never surface raw
   flags / HTTP codes / JSON unless the user asks for the technical detail.
6. **Refer to the account only by its wallet address — never the internal account
   id** in normal conversation. If a response carries an `accountId` / `aid` and the
   user did not ask for it, identify the account by its `0x…` address only.
7. Flows chain via a **session wallet** (`~/.upside_test.<host>.json`): run any
   flow once (they auto-register) and the rest reuse the same account.

## Flow menu

| Flow | Command | What the user sees |
| --- | --- | --- |
| 一键全流程 Full | `play.py full` | account → balance → a resting limit order placed 20% below the mark, then cancelled (no position opened) |
| 注册 Register | `play.py register` | New wallet → register → balance check (the key is saved locally, never shown) |
| 下单 Order | `play.py order` | Places a trade (auto-registers first); says whether it filled or is resting |
| 平仓 Close | `play.py close` | Closes any open position |
| 查询账户 Status | `play.py status` | Wallet, balance, open positions |
| 查询订单 Orders | `play.py orders` | Resting/open orders with their `id` |
| 查询仓位 Positions | `play.py positions` | Open positions + balances |
| 撤单 Cancel | `play.py cancel --all` | Cancels one (`--oid N`) or all open orders |
| 实时行情 Live stream | `play.py ws trades` | Pretty-printed live feed (`l2Book`/`bbo`/`trades`/`candle`) |
| 价格滚动 Ticker | `play.py ticker` | A compact live mark/bid/ask ticker |
| 概念讲解 Explain | `play.py explain leverage` | Plain explanation (perp/leverage/limit/market/margin/funding/mark/tif) |
| 导览 Tour | `play.py tour` | Narrated walkthrough, then runs `full` |
| 导出 Export | `play.py export` | Saves the wallet to `.env` (mode 600) so the `examples/` scripts use this account |
| 重置 Reset | `play.py reset` | Moves the session wallet aside (to a timestamped backup file) and starts fresh |

**Recommended first experience:** `full` — it shows the order lifecycle without
opening a position.

### Useful flags (only when asked)

- `play.py order --side sell --price 64000 --size 0.01 --contract 1` — customize the trade (pass the **display** price/size; the launcher scales to raw)
- `play.py order --show-code` — also print the exact signed request (bridge to real integration)
- `play.py order --again` — repeat your last order's parameters
- `play.py ws candle --asset 1 --interval 1m --duration 30`
- `--lang zh` on any command for native Chinese output

## Things to tell the user (so results aren't confusing)

- **Which environment.** The test drive defaults to Devnet
  (`https://dev.upsidemax.xyz`), a test environment; Mainnet (`https://upsidemax.xyz`)
  is real funds. The menu header shows which one.
- **A new account is empty.** There is no automatic credit on any environment.
  Devnet funds: contact the UpsideMAX team. Mainnet: deposit funds into the account.
- **Orders may be accepted asynchronously.** A placed order can return
  `status: "accepted"` with `{ "count": 1 }` — the order `id` is **not** in that
  response; the script reads it back from `userOrders`. This is expected.
- **`priceReady: false`** on a contract means it has no usable price yet; the
  script picks another contract.
- **WebSocket** handshakes need a `User-Agent` header (the script sets it); a bare
  client gets a `403`.

## Going deeper (hand off to the focused skills)

The test drive is for a quick taste. When the user wants real depth, route to:

- Account internals, funding layers, migration → [`../upside-onboarding/SKILL.md`](../upside-onboarding/SKILL.md)
- Full order types, modify, leverage, market data → [`../upside-trading/SKILL.md`](../upside-trading/SKILL.md)
- All WebSocket channels + payload shapes → [`../upside-websocket/SKILL.md`](../upside-websocket/SKILL.md)
- Agent delegation, TP/SL, decoding numeric error codes → [`../upside-advanced/SKILL.md`](../upside-advanced/SKILL.md)

A per-flow reference (defaults, flags, output shape) is in
[`references/flows.md`](references/flows.md).

## Security & notes

- **Invitation code required.** Registration needs an invitation code on Mainnet
  and Devnet. If a flow reports that no code is set, ask the user for theirs (they
  request one from the UpsideMAX team), then pass it inline on the command — do
  **not** invent a code:
  `UPSIDE_INVITE_CODE=<code> python3 "${CLAUDE_PLUGIN_ROOT}/skills/upside-test/scripts/play.py" full`
- **No manual pre-flight.** The launcher self-installs its Python dependencies on
  first run and reports any connectivity error itself — do not probe imports or
  `curl` the API before running a flow.
- **Never** ask the user to paste a private key. The script generates its own and
  never prints it.
- On Mainnet the session file holds a key that controls real funds. Never read it into the
  conversation; tell the user where it is so they can back it up.
