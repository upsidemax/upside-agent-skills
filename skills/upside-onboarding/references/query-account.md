# Query Account

Read `userAccount` to inspect balance, positions, and account config. Read-only; no signing.

## Workflow

1. **Confirm you have an `accountId`.** If not, run [register](register.md) first.
2. **Read both layers** (mo=0 for DexLedger, MO=1 for market margin):
   ```bash
   python3 examples/03_check_balance.py <aid>
   ```
   Or inline via `common.get_balance(aid)` → `(mo0_raw, mo1_raw)`.
3. **Interpret the two layers**:
   - `mo=0` `chainBalances` — funds not yet locked into any market (can't back orders)
   - `MO=1` `crossCollaterals` — funds locked as margin for Market #1 (can back orders)
4. **Render the Balance Summary template** to the user.
5. **Route on outcome**:
   - `MO=1 crossCollateral > 0` → user is ready to trade. Route to [`../../upside-trading/SKILL.md`](../../upside-trading/SKILL.md).
   - Only `mo=0` has funds → suggest `lockCollateral` to migrate.
   - Both 0 → see [auto-airdrop](auto-airdrop.md) (airdrop miss recovery is to register a fresh wallet).

## Query

```json
{"type": "userAccount", "accountId": "<aid>", "marketDeployerId": <0 or N>}
```

**Critical**: the field name is `marketDeployerId`. See [the `marketDeployerId` field](#the-marketdeployerid-field).

## The `marketDeployerId` field

Balance and account queries select which layer to read via the `marketDeployerId` field: `0` for the DexLedger view, `N` for the margin view of Market #N. Always pass `marketDeployerId` on `userAccount` queries.

## Response schema (MO=1 view)

```json
{
  "type": "userAccount",
  "accountId": "5",
  "marketDeployerId": 1,

  "crossEquity": "1000000000000",
  "orderFrozen": "0",
  "orderLoss": "0",
  "marginAvailable": "1000000000000",
  "marginAvailableForOrder": "1000000000000",

  "totalPositionIM": "0",
  "crossPositionMM": "0",

  "marginShareType": "Unified",
  "depositNonce": "1",
  "takerOverrideBps": -32768,
  "makerOverrideBps": -32768,

  "crossCollaterals":    [{"coinId":1,"amount":"1000000000000"}],
  "isolatedCollaterals": [],
  "chainBalances":       [],
  "positions":           [],
  "portfolioGroups":     [],
  "contractSettings":    []
}
```

Field-by-field:

| field | meaning |
|---|---|
| `crossEquity` | total value in this market (raw units of `settleCoin`) |
| `orderFrozen` | margin locked by open orders (increases when order enters book) |
| `orderLoss` | unrealized loss on open orders (rarely non-zero on QA) |
| `marginAvailable` | `crossEquity - orderFrozen - positionIM` — what's free right now |
| `marginAvailableForOrder` | same as above minus reserves; use this to check before placing an order |
| `totalPositionIM` | initial margin needed for currently-open positions |
| `crossPositionMM` | maintenance margin (liquidation threshold) |
| `marginShareType` | `Unified` (single cross pool) or `Portfolio` (per-group pools) |
| `depositNonce` | monotonic; `0` = never received funds |
| `takerOverrideBps` / `makerOverrideBps` | `-32768` sentinel = "no override" |
| `crossCollaterals` | list of `{coinId, amount}` cross-margin balances |
| `isolatedCollaterals` | per-position isolated margin (rare) |
| `chainBalances` | always `[]` at MO≥1 view; query with `marketDeployerId: 0` |
| `positions` | open positions in this market |
| `portfolioGroups` | non-empty only when `marginShareType: "Portfolio"` |

## Response schema (mo=0 view)

```json
{
  "type": "userAccount",
  "accountId": "5",
  "marketDeployerId": 0,

  "chainBalances":       [{"coinId":1,"amount":"1000000000000"}],
  "crossCollaterals":    [],
  "isolatedCollaterals": [],
  "positions":           [],
  "depositNonce":        "1",
  // most numeric fields are 0 at mo=0
}
```

`chainBalances` at mo=0 is the DexLedger ledger. To trade, you must migrate to MO=N via `enrollUserToMarketOwner` + `lockCollateral`.

## Template — Balance Summary

Ready to trade:
```
✓ Account Balance (Upside QA)

  Account ID:              {aid}
  DexLedger (mo=0):        {usdt_mo0_formatted}
  Market #1 margin:        {usdt_mo1_formatted}
  Available for order:     {avail_formatted}
  Open positions:          {n_positions}
  Open orders locked:      {order_frozen_formatted}

  Status: Ready to trade
```

Needs migration (mo=0 only):
```
⚠ Account has funds in DexLedger only — not tradeable yet

  Account ID:              {aid}
  DexLedger (mo=0):        {usdt_mo0_formatted}
  Market #1 margin:        0 USDT

  To trade, migrate mo=0 → MO=1:
    1. enrollUserToMarketOwner (marketDeployerId=1)
    2. lockCollateral (marketDeployerId=1, coinId=1, amount=…)
```

Empty:
```
⚠ Account has no funds

  Account ID:              {aid}
  depositNonce:            {dn}
  Suggested:               {if dn==0: "wait for airdrop; if >60s, register a fresh wallet" | "check with support"}
```

## Confirming Response

Read-only. **Skip** the Confirming gate.

## Numeric conversions

All `amount` fields are decimal strings in **raw units** (multiplied by `10**szDecimals`). Both USDC and USDT are `szDecimals=6`; BTC/ETH/SOL are `szDecimals=8`. Auto-detect via `/info configs.coins[]`. Convert:

```python
raw = int(r["chainBalances"][0]["amount"])
usdt = raw / 10**6
```

Follow [_shared/amount-display.md](../_shared/amount-display.md) for how to render.

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| All fields `null` | wrong field name in the query | use `marketDeployerId` |
| `chainBalances: []` but `depositNonce > 0` | funds landed in MO=1 (not mo=0) | query with `marketDeployerId: 1` |
| `crossCollaterals: []` but `depositNonce > 0` | funds landed in mo=0 | query with `marketDeployerId: 0` |
| Response for a non-existent `aid` — default empty struct | not a 404 error | attempt `registerAccount` to distinguish "unregistered" from "registered-but-empty" |

## See also

- [register](register.md) — get an accountId
- [auto-airdrop](auto-airdrop.md) — get funds into the account
- [`../../upside-trading/references/user-orders.md`](../../upside-trading/references/user-orders.md) — separate query for open orders
- [_shared/amount-display.md](../_shared/amount-display.md) — how to render numbers
