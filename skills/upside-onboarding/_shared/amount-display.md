# Amount Display Rules

> Shared across all Upside skills. Apply these rules any time you render numeric amounts, addresses, or IDs to the user.

## Settle-coin amounts (auto-detected via `/info configs`)

**Do NOT hardcode the settle coin as USDT** — the chain can initialize with either USDC or USDT depending on its configuration. Discover it via `/info configs`:

```json
POST /info { "type": "configs" }
→ { "coins": [...], "marketDeployers": [{ "marketDeployerId": 1, "settleCoinId": 1, ... }], ... }
```

Then look up the coin: `coins.filter(c => c.coinId === settleCoinId)` gives `{name, szDecimals}`.

Backend returns raw units as decimal strings. Convert for display:

```
human = int(raw) / 10**settle.szDecimals
```

Formatting (using the detected coin name):

| range | format |
|---|---|
| `>= 1` | `1,000,000.00 <name>` — 2 decimals, thousands-separator |
| `< 1` and `> 0` | `0.001234 <name>` — up to `szDecimals` decimals, no trailing zeros |
| `0` | `0 <name>` — bare zero, no `.00` |

Where `<name>` is `USDT` or `USDC` (or whatever the chain declared). Never show raw units to the end user; they're multiple orders of magnitude off. Reserved for raw JSON dumps in debug output.

Python reference implementation: [`common.py::format_amount`](../../../examples/common.py) — reads `/info configs`, caches the metadata, and picks the right `name` + `szDecimals`. Use `format_amount(raw)` for the market's settle coin, or `format_amount(raw, coinId=<id>)` for any other coin.

## Contract prices

Prices are decimal strings scaled by the contract's `priceScale` (usually 2 on QA):

```
human = int(mark_px_string) / 10**price_scale
```

Rendering:

| range | format |
|---|---|
| `>= 100` | `1,234.56` — 2 decimals |
| `1 – 100` | `1.2345` — 4 decimals |
| `< 1` | `0.000123` — up to 8 decimals, no trailing zeros |

For `priceReady: false`, render as `— (no oracle price)` — not "0".

## Sizes / positions

Sizes are decimal strings in the contract's qty units. Scale by `qtyScale` (usually 4 on QA):

```
human = int(size_string) / 10**qty_scale
```

Never lose precision — round only for display, keep the raw string for further calls.

## Addresses (funds-loss risk)

**Always verbatim, character-for-character, from the most recent response.** Never:

- Paraphrase (`0x0abc...ec52` → `0xabc...52`)
- Fix case (`0xABC...` → `0xabc...`)
- Insert spaces or line-break inside an address
- Reproduce an address from memory across turns — re-read it from the source

If shortening for readability, use the exact form `0xLLLLLL…RRRRRR` (6 chars head + `…` + 6 chars tail), and only when the full form is also present somewhere in the same turn.

## Account IDs

`accountId` is a small integer as a string. Render as bare digits: `aid=5`. Never zero-pad, never reformat.

## Transaction / order IDs

Order `id` and `oid` are integers as strings. Render as bare digits. Never truncate.

## errorCode

Numeric. Render as `errorCode: <n>` followed by the message. Both `errorCode` and `errorMessage` should appear together — one without the other loses information.

## When to include units

Every amount MUST carry its unit token: `USDT`, `USD`, or the contract's `settleCoin` symbol. Never bare numbers for money.

## Language / locale

Match the user's language. If ambiguous, default to English. Numbers use `1,234.56` (comma thousands, period decimal). If the user is writing in a locale that uses `1.234,56`, follow their convention.
