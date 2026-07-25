# TP/SL — Conditional Entries

Automated take-profit and stop-loss for an open position. Backed by conditional orders that sit `Untriggered` until the trigger price is crossed.

## Workflow

### Attach TP/SL to a position

1. **Verify a position exists** on the target contract (check `userAccount.positions[…]`). No position → TP/SL will be created but never trigger anything.
2. **Compute correct side**:
   - Long position (`positionSide=0`, or OneWay net-long): TP MUST be `> currentPrice`, SL MUST be `< currentPrice`.
   - Short: reverse.
3. **Show Confirming Response**. See [Confirming Response](#confirming-response).
4. **Run**:
   ```bash
   python3 examples/09_tpsl.py <priv_key> <contractId> <tpPrice> [slPrice]
   ```
5. **Verify** via `userOrders` — look for entries with `isConditional: true, status: "Untriggered"`.
6. **Render the TP/SL Attached template**.

### Cancel TP/SL

1. **Confirm the target** — show current TP/SL entries via `userOrders`.
2. **Show Confirming Response**.
3. **Run** cancelTpSl (removes both TP and SL for the position side):
   ```bash
   python3 examples/09_tpsl.py cancel <priv_key> <contractId>
   ```
   Or cancel a specific one via `cancel` with the `oid`.
4. **Render the TP/SL Cancelled template**.

## tpSl — action

```json
{
  "type": "tpSl",
  "a": 1,                          // contractId
  "positionSide": 0,               // 0 = long / OneWay, 1 = short
  "isPositionTpsl": true,          // bind to whole position (recommended)
  "tpPrice": "1500",               // optional
  "slPrice": "400",                // optional
  "tpTriggerType": 0,              // 0 = last, 1 = mark, 2 = index
  "slTriggerType": 0
}
```

Rules:
- At least one of `tpPrice` / `slPrice` MUST be set.
- Prices are decimal strings, same scale as regular order prices.

## Response

```json
{
  "type": "tpSl",
  "data": {
    "tpOrderId": 12345,          // oid of the created TP entry (0 if not set)
    "slOrderId": 12346           // oid of the created SL entry (0 if not set)
  }
}
```

If `errorCode: 1 "invalid trigger price"`, the TP/SL price was on the wrong side of the position.

## Trigger types

| value | price source | characteristics |
|:---:|---|---|
| **0** | `lastPx` (last trade) | fires on any single trade — vulnerable to wick |
| **1** | `markPx` (mark price) | funding-weighted composite — smoother, harder to grief |
| **2** | `oraclePx` (oracle index) | off-chain aggregated — most independent |

Common defaults:
- **Stops**: `1` (mark price) — resistant to short-term manipulation
- **Take-profits**: `0` (last price) — fires as fast as possible on a favorable move

## cancelTpSl — action

```json
{"type": "cancelTpSl", "a": 1, "positionSide": 0}
```

Cancels **both** TP and SL for the `(contract, positionSide)`. Response:
```json
{"cancelledCount": 2}
```

To cancel just one (e.g. only the SL), use `cancel` with the specific `oid`:
```json
{"type":"cancel", "cancels":[{"a": 1, "o": 12346}]}
```

## OneWay vs Hedge mode

- **OneWay** (default on QA): one net position per contract. Always use `positionSide: 0`.
- **Hedge** (not enabled on QA by default): separate long / short positions. Use `positionSide: 0` for long, `1` for short.

Verify via `userAccount.positions[0].positionSide`. If it says `"OneWay"`, use `0`.

## Where TP/SL show up

### userOrders

```json
{
  "id": "12345",
  "contractId": 1,
  "orderSide": "S",              // opposite side of the position
  "orderType": "TPM",            // "TPM" = take-profit market, "SLM" = stop-loss market
  "positionSide": "OneWay",
  "triggerPrice": "1500",
  "triggerPriceType": 0,
  "price": "0",                  // resolved at trigger time
  "size": "0",                   // resolved at trigger time (full position by default)
  "reduceOnly": true,            // always true for TP/SL
  "parentOrderId": "0",
  "isConditional": true,         // key marker
  "status": "Untriggered"        // → "Triggered" → "Filled" or "Canceled"
}
```

### WebSocket orderUpdates

Same fields, streamed live. See [`../../upside-websocket/references/payload-samples.md`](../../upside-websocket/references/payload-samples.md#orderupdates--tp-created-conditional).

**Legacy field alias**: this field may appear as `cond: true` instead of `isConditional: true`. Handle both:

```python
def is_conditional(o):
    return o.get("isConditional") is True or o.get("cond") is True
```

## Lifecycle

```
attach tpSl → status "Untriggered"
    │
    │ (market price crosses trigger)
    ▼
status "Triggered"
    │
    │ (matching engine executes market close)
    ▼
status "Filled" (or "PartiallyFilled" if insufficient liquidity)
```

Or explicit cancel:
```
"Untriggered" → cancelTpSl → status "Canceled"
```

## Templates

### Confirming Response — attach

```
⚠  About to ATTACH TP/SL on Upside (QA).

  Account:       {aid} — {addr_short}
  Contract:      {contractId} ({symbol_if_known})
  Position side: {OneWay|Long|Short}
  Current mark:  {mark_formatted}

  Take profit:   {tp_formatted}  (trigger: {last|mark|index})
  Stop loss:     {sl_formatted}  (trigger: {last|mark|index})

  When triggered, the full position size will be closed at market price.
  Conditional orders are reduce-only.

Reply "yes" to proceed, anything else to cancel.
```

### TP/SL Attached

```
✓ TP/SL attached on Upside (QA)

  Account:      {aid}
  Contract:     {contractId}
  TP order:     oid={tpOrderId}  trigger={tp_formatted}  ({trigger_type})
  SL order:     oid={slOrderId}  trigger={sl_formatted}  ({trigger_type})

  Cancel:       python3 examples/09_tpsl.py cancel <priv> {contractId}
```

### Confirming Response — cancel

```
⚠  About to CANCEL TP/SL on Upside (QA).

  Account:       {aid}
  Contract:      {contractId}
  Position side: {sides}
  Will cancel:   {tp_summary} + {sl_summary}

  Cancel removes both TP and SL for this position side.
  Your position is unaffected.

Reply "yes" to proceed, anything else to cancel.
```

### TP/SL Cancelled

```
✓ TP/SL cancelled on Upside (QA)

  Account:         {aid}
  Contract:        {contractId}
  Cancelled count: {cancelledCount}
```

## Confirming Response

- `tpSl` (attach): **always confirm** — creates automated close orders
- `cancelTpSl`: **always confirm** — removes automated risk management
- `userOrders` (list): **skip** — read-only

## Common pitfalls

- **No position, no trigger**: backend accepts `tpSl` (`http 200` with `tpOrderId`), but the conditional will never fire because there's nothing to reduce. Always verify `userAccount.positions[…]` before attaching.
- **TP/SL on wrong side**: TP on long < current → `errorCode: 1 "invalid trigger price"`. Compute the correct side before submitting.
- **positionSide mismatch on hedge mode**: creates an orphan conditional that never triggers. Verify mode before use.
- **Trigger type semantics**: last-price triggers can fire on a single stale print. Use mark for stops on illiquid contracts.

## Common failure modes

| code | message | fix |
|---:|---|---|
| 1 | `invalid trigger price` | put the price on the correct side of current price |
| 4 | `unknown contract` | check contractId via `marketState` |
| 30 | `agent may sign trade actions only` | signer is agent trying to sign non-TRADE — but `tpSl` IS TRADE. Check `userAgents` |

## See also

- [agent-delegation](agent-delegation.md) — agents can manage TP/SL
- [error-codes](error-codes.md) — full errorCode table
- [`../../upside-trading/references/user-orders.md`](../../upside-trading/references/user-orders.md) — where TP/SL entries live
- [`../../upside-websocket/references/payload-samples.md`](../../upside-websocket/references/payload-samples.md) — WS shape for TP/SL updates
- [_shared/confirming-response.md](../../upside-onboarding/_shared/confirming-response.md) — safety gate
