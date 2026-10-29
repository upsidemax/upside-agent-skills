# Test Drive flows — reference

Every flow is a subcommand of `skills/upside-test/scripts/play.py`. The script
reuses the helpers in `examples/common.py` (signing, HTTP, configs,
balances) — it adds no new protocol logic. Run from the repo root.

## Session wallet

The launcher defaults to **Devnet** (`https://dev.upsidemax.xyz`); set
`UPSIDE_BASE_URL=https://upsidemax.xyz` for Mainnet.

State lives in `~/.upside_test.<host>.json` — one file per environment
(`~/.upside_test.dev.upsidemax.xyz.json` for Devnet,
`~/.upside_test.upsidemax.xyz.json` for Mainnet), mode 600:

```json
{ "private_key": "0x…", "address": "0x…", "account_id": "284", "base_url": "https://dev.upsidemax.xyz" }
```

- Written by `register` / `order` / `full` (any flow that needs an account).
- Read by `status` / `positions` / `orders` / `cancel`.
- `reset` moves it to a timestamped backup next to it — a key is never deleted.
- On Mainnet it holds a real key: never read it into the conversation, never print it.

## Commands

Output is **plain-language** (`✓ Order placed…`, `💰 … available to trade`) — raw HTTP
codes / JSON are intentionally hidden. Every standalone flow ends with a
`→ Next:` suggestion. Relay these to the user in their language.

A global `--lang en|zh` (or env `UPSIDE_LANG`) switches the output language.

| Command | Flags (defaults) | Does | Key output |
| --- | --- | --- | --- |
| `menu` | — | Flow list + session summary (orders/positions) | menu |
| `full` | `--contract` `--price` `--size` | account → balance (stops if zero) → limit buy 20% below mark at the minimum order value → cancel it | `✓ Order submitted…` + `✓ Cancelled…` |
| `register` | — | new wallet → `registerAccount` → one balance check (zero → Devnet: contact the team; Mainnet: deposit) | `🎉 Account created` + balance line |
| `order` | `--side buy` `--price <mark>` `--size 1` `--contract <auto>` `--tif Gtc` `--show-code` `--again` | auto-registers, places a limit order, detects fill vs resting | `✓ Order placed…` → `🎯 filled` / resting id |
| `close` | — | reduce-only opposite order to flatten each open position | `✓ Sent close…` + remaining count |
| `status` | — | Balance + positions | balance + positions |
| `positions` | — | Positions + all collateral balances | positions + balances |
| `orders` | — | Active orders from `userOrders` | `#id Buy/Sell size contract @ price (status)` |
| `cancel` | `--oid N` \| `--all` | Cancels first / specific / all open orders | `✓ Cancelled order #N` |
| `ws` | `channel` `--asset 1` `--interval 1m` `--duration 15` | Subscribes + **pretty-prints** (📖 book / 🟢🔴 trades / 🕯 candle / 🔔 orders) | formatted stream |
| `ticker` | `--contract <auto>` `--duration 15` | Compact live mark/bid/ask via `l2Book` | rolling price line |
| `explain` | `<topic>` | Plain-language concept (perp/leverage/limit/market/margin/funding/mark/tif) | one-liner |
| `tour` | — | Narrated 5-step walkthrough, then runs `full` | narration + full |
| `export` | `--path` | Writes the session wallet to `.env` for the `examples/` scripts | `.env` path |
| `reset` | — | Moves the session wallet to a timestamped backup | backup path |

- Contract/price default to an **auto-picked live USDC contract** at its **mark price** (not a hardcoded id / unrealistic 100).
- After each state-changing flow, a one-line **account snapshot** (balance · orders · positions) shows the effect.

## Behaviors worth knowing

- **Async order response.** `order` returns `{"status":"accepted","response":{"type":"order","data":{"count":1}}}`.
  There is no `oid` in that body; the script resolves the order id from a
  follow-up `userOrders` query.
- **`priceReady=false`.** The contract has no usable price yet; `full` stops and
  asks for another contract.
- **Zero balance.** A new account is empty on every environment. The script stops
  — Devnet: contact the UpsideMAX team for Devnet funds; Mainnet: deposit funds into
  the account. No polling, no re-registering.
- **Funding layer.** Only MO=1 cross collateral can trade. Funds at mo=0 (chain
  level) need an `enrollUserToMarketOwner` + `lockCollateral` migration — route to
  `upside-onboarding`.
- **WS 403.** Handshakes without a `User-Agent` are refused; the script sends a
  `User-Agent` and an `Origin` matching the base URL.

## Extending

To add a flow, add a `cmd_*` function in `scripts/play.py` and wire it into the
`argparse` dispatch. Reuse `common.py` helpers (`send_exchange`, `info`,
`get_balance`, `get_contract`, `format_amount`) instead of re-implementing
signing or HTTP.
