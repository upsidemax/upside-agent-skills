# Place Order (and Modify, updateLeverage)

Place a limit / IOC / FOK / post-only order. Fire-and-forget: HTTP `202` fast, matching happens async.

## Workflow

1. **Pre-flight** (do this in order):
   1. Read [market-state](market-state.md) → verify `priceReady: true`. If false, warn and confirm intent before proceeding.
   2. Read [`../../upside-onboarding/references/query-account.md`](../../upside-onboarding/references/query-account.md) → verify `marginAvailableForOrder >= estimated_notional`. If insufficient, refuse and suggest `lockCollateral` or reducing size.
   3. Estimate notional: `size × price` in raw units; render to human USDT per [_shared/amount-display.md](../../upside-onboarding/_shared/amount-display.md).
2. **Show Confirming Response**. See [Confirming Response](#confirming-response). Do NOT skip.
3. **Run**:
   ```bash
   python3 examples/05_place_order.py <priv_key> <contractId> <price> <size> <buy|sell>
   ```
4. **Wait 2 seconds** then verify entry via [user-orders](user-orders.md).
5. **Render the Order Placed template**.

## Action envelope shape

```json
{
  "type": "order",
  "grouping": "na",
  "orders": [
    {
      "a": 1,                          // contractId
      "b": true,                       // true = buy, false = sell
      "p": "6400000",                  // RAW price = display 64000.00 × 10^priceScale(2)
      "s": "10000",                    // RAW size  = display 1 × 10^qtyScale(4)
      "r": false,                      // reduce-only
      "c": "0x000…001",                // optional client order id (0x + 63 hex)
      "t": {"limit": {"tif": "Gtc"}}   // Gtc | Ioc | Fok | Alo
    }
  ]
}
```

Batch: pass multiple orders in the `orders` array. On QA, prefer 1-at-a-time for reliability (batches above ~5 sometimes hit `504 DOWNSTREAM_TIMEOUT`).

## Precision — convert display → raw before signing (critical)

`p` and `s` go on the wire as **raw integers**, not the human numbers the user
says. This is the #1 source of silently-wrong orders: a user's "sell @ 70000"
must be signed as `p:"7000000"`, **not** `p:"70000"` (which the engine reads as
700.00 — an accidental market dump).

Read the scales from the contract in `/info configs` — **never hardcode them**:

```python
c = get_contract(contract_id)          # from configs
price_raw = round(display_price * 10 ** c["priceScale"])   # snap to c["tickSize"]
size_raw  = round(display_size  * 10 ** c["qtyScale"])     # snap to c["stepSize"]
```

- Use exact decimal arithmetic (Python `Decimal`, JS integer math) — floats
  drift on values like `0.1 × 10^4`.
- Snap to the contract's `tickSize` / `stepSize` (both `1` on QA today).
- On QA the majors are `priceScale = 2`, `qtyScale = 4`; **read the real values
  per contract** rather than assuming — other markets differ.
- Going the other way (raw → display) for confirmations and readback:
  [_shared/amount-display.md](../../upside-onboarding/_shared/amount-display.md).
- The launcher does exactly this in `_px_to_raw` / `_sz_to_raw`
  ([`play.py`](../../upside-test/scripts/play.py)) — mirror it.

Coin **amounts** (balances, collateral) use the coin's own `szDecimals`
(USDC = 6), a separate scale from the contract price/qty scales above.

## Field reference

| field | type | required | meaning |
|---|---|:---:|---|
| `a` | int | ✅ | contractId |
| `b` | bool | ✅ | true = buy, false = sell |
| `p` | string | ✅ | limit price as a **raw integer string** = `display × 10^priceScale`, snapped to `tickSize` (see [Precision](#precision--convert-display--raw-before-signing-critical)) |
| `s` | string | ✅ | order size as a **raw integer string** = `display × 10^qtyScale`, snapped to `stepSize` |
| `r` | bool | ✅ | reduce-only flag |
| `c` | string | ❌ | client order id (cloid). `0x` + 63 hex chars. Unique per account per contract |
| `t` | object | ✅ | order type wrapper (see below) |
| `builderAddress` | string | ❌ | builder-fee recipient (`0x` + 40 hex). Omit = no builder. An unregistered address does **not** reject the order — `builderFee` is silently zeroed |
| `builderFee` | int | ❌ | builder fee, in basis points. Ignored when `builderAddress` is omitted |

`builderAddress` / `builderFee` sit **inside each order object** (alongside `a`/`b`/`p`/`s`/`t`), not at the action top level. In a batch, only **`orders[0]`'s** builder fields take effect — the engine applies them as the single shared builder for the whole request.

## Time-in-force (`t.limit.tif`)

| tif | behavior |
|---|---|
| `Gtc` | Good-till-cancel. Standard limit. Rests on book until filled or cancelled. |
| `Ioc` | Immediate-or-cancel. Fills what's possible immediately; cancels the rest. |
| `Fok` | Fill-or-kill. All-or-nothing; either fully fills or fully cancels. |
| `Alo` | Add-liquidity-only (post-only). Rejects if it would take liquidity. |

Market orders are represented as `Ioc` with an aggressive price. No separate `"market"` type in the wire protocol.

## `grouping`

- `"na"` — no grouping (default; use for plain `order`)
- Other values (`"normalTpsl"`) are used by `tpSl` action. Not applicable here.

## Modify

```json
{
  "type": "modify",
  "oid": 12345,
  "order": {"a": 1, "b": true, "p": "6410000", "s": "20000", "r": false, "t": {"limit": {"tif": "Gtc"}}}
  // p/s are RAW (display × 10^scale), same as place-order — see Precision above
}
```

Modifies price/size/tif of an existing order. Note: if the order has partially filled, modify replaces the remaining size only. Warn the user before modifying a partially filled order.

## updateLeverage

```json
{"type": "updateLeverage", "a": 1, "leverage": 5, "isIsolated": false}
```

Changes leverage for the contract (or specific position if isolated). Impacts existing positions immediately — maintenance margin recomputed. Show before/after in the confirmation prompt.

## Response

HTTP layer:
```json
{
  "http": 202,
  "status": "accepted",
  "requestId": "req-…",
  "response": {
    "type": "order",
    "data": {"count": 1}
  }
}
```

`data.count` = number of orders in the envelope that reached the matching queue. **NOT** the number that entered the book. To confirm the order actually landed, query [user-orders](user-orders.md) after ~1-3 s.

## When the matching engine silently drops your order

Even with `http 202`:

- `priceReady: false` → price band validation fails
- `p` outside price band (`markPx * (1 ± priceBandBps/10000)`) → dropped silently
- `marginAvailableForOrder < required` → dropped
- `r: true` (reduce-only) but no matching position → dropped
- Contract paused / delisted → dropped

Detection: after 2-3 s, `userOrders` still returns 0 for that account/contract AND `userAccount.orderFrozen` is unchanged.

## Cloid rules

- Scoped per-account per-contract.
- Same cloid twice on same contract → 2nd rejected.
- Format: `0x` + 63 hex chars. Enforce; wrong length = rejected.
- Optional but strongly recommended for automated systems (client-side idempotency for retries).

## Template — Confirming Response (before placing)

Render **verbatim** per [_shared/confirming-response.md](../../upside-onboarding/_shared/confirming-response.md):

```
⚠  About to PLACE ORDER on Upside (QA).

  Account:   {aid} — {addr_short}
  Contract:  {contractId} ({symbol_if_known})
  Side:      {buy|sell}
  Type:      {Gtc|Ioc|Fok|Alo} limit
  Price:     {price_formatted}
  Size:      {size_formatted}
  Notional:  ≈ {notional_usdt}
  Reduce-only: {yes|no}

  This action will consume ~{margin_usdt} of margin.
  Fills are irreversible.

Reply "yes" to proceed, anything else to cancel.
```

## Template — Order Placed

After confirmation + successful submit + verified in `userOrders`:

```
✓ Order placed on Upside (QA)

  Order ID:   {oid}
  Contract:   {contractId}
  Side:       {buy|sell} @ {price_formatted}
  Size:       {size_formatted}
  Type:       {tif}
  Status:     {Open|PartiallyFilled|Filled}
  cloid:      {cloid_or_-}

  To cancel:  python3 examples/06_cancel_order.py cancel {priv} {contractId} {oid}
```

If `userOrders` shows 0 after 3 s despite `http 202`:

```
⚠ Order was accepted (HTTP 202) but never entered the book.

  Most likely cause: {priceReady: false | insufficient margin | price outside band}

  Diagnosis:
    python3 examples/04_market_info.py {contractId}   # check priceReady + band
    python3 examples/03_check_balance.py {aid}         # check marginAvailableForOrder
```

## Confirming Response

**Every** order placement, modify, and updateLeverage MUST pass through the Confirming gate. See [_shared/confirming-response.md](../../upside-onboarding/_shared/confirming-response.md).

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| `http 202` but `userOrders` count = 0 | matching engine drop (priceReady / margin / band) | see [when the matching engine silently drops](#when-the-matching-engine-silently-drops-your-order) |
| `errorCode: 30` | signer is agent, trying to sign non-TRADE — but `order` IS TRADE. Something's wrong. | check `userAgents`; agent may have been revoked |
| `errorCode: 4 "unknown contract"` | contractId doesn't exist | check `marketState` |
| `http 400 "invalid asset"` | passed non-numeric `a` | use int |
| `errorCode: 31 "nonce already used"` | replay | regenerate the envelope |

## See also

- [market-state](market-state.md) — pre-flight for `priceReady`
- [cancel-order](cancel-order.md) — remove the order
- [user-orders](user-orders.md) — verify entry into the book
- [`../../upside-advanced/references/tpsl.md`](../../upside-advanced/references/tpsl.md) — conditional entries
- [_shared/confirming-response.md](../../upside-onboarding/_shared/confirming-response.md) — the safety gate
- [_shared/amount-display.md](../../upside-onboarding/_shared/amount-display.md) — how to render prices and sizes
