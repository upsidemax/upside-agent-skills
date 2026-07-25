# Test Drive flows — reference

Every flow is a subcommand of `skills/upside-test/scripts/play.py`. The script
reuses the QA-validated helpers in `examples/common.py` (signing, HTTP, configs,
balances) — it adds no new protocol logic. Run from the repo root.

## Session wallet

State lives in `~/.upside_test.json`:

```json
{ "private_key": "0x…", "address": "0x…", "account_id": "284" }
```

- Written by `register` / `order` / `full` (any flow that needs an account).
- Read by `status` / `positions` / `orders` / `cancel`.
- `reset` deletes it. QA-only testnet key — no real value.

## Commands

Output is **plain-language** (`✓ Order placed…`, `💰 Funded with…`) — raw HTTP
codes / JSON are intentionally hidden. Every standalone flow ends with a
`→ Next:` suggestion. Relay these to the user in their language.

A global `--lang en|zh` (or env `UPSIDE_LANG`) switches the output language.

| Command | Flags (defaults) | Does | Key output |
| --- | --- | --- | --- |
| `menu` | — | Flow list + session summary (orders/positions) | menu |
| `full` | `--contract` `--price` `--size` `--show-key` | register → airdrop → **sell into the bid to open a real position** → show PnL → close | `🎯 It filled…` + close |
| `register` | `--show-key` | new wallet → `registerAccount` → poll airdrop (≤45s, live countdown, one auto-retry) | `🎉 account created` + `💰 funded` |
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
| `reset` | — | Forgets the session wallet | confirmation |

- Contract/price default to an **auto-picked live USDC contract** at its **mark price** (not a hardcoded id / unrealistic 100).
- After each state-changing flow, a one-line **account snapshot** (balance · orders · positions) shows the effect.

## Behaviors worth knowing

- **Async order response.** `order` returns `{"status":"accepted","response":{"type":"order","data":{"count":1}}}`.
  There is no `oid` in that body; the script resolves the order id from a
  follow-up `userOrders` query. (Matches the public docs' documented QA behavior.)
- **`priceReady=false`.** The order is accepted (`202`) but the matching engine
  drops it. The script prints a warning; nothing errors.
- **Airdrop layer.** Funds arrive as MO=1 cross collateral (tradeable). If they
  ever land only in mo=0 (ledger), trading needs a `lockCollateral` migration —
  out of scope here; route to `upside-onboarding`.
- **WS 403.** The QA WebSocket sits behind CloudFront and rejects bare clients;
  the script sends a browser `Origin` + `User-Agent` on the handshake.

## Extending

To add a flow, add a `cmd_*` function in `scripts/play.py` and wire it into the
`argparse` dispatch. Reuse `common.py` helpers (`send_exchange`, `info`,
`get_balance`, `get_contract`, `format_amount`) instead of re-implementing
signing or HTTP.
