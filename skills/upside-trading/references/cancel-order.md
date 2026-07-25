# Cancel Order (single, by cloid, and cancelAll)

Three variants. All fire-and-forget (`http 202`).

## Workflow

### Cancel one order by oid

1. **Skip Confirming gate** if the user explicitly named the oid (they know what they're cancelling).
2. **Run**:
   ```bash
   python3 examples/06_cancel_order.py cancel <priv_key> <contractId> <oid>
   ```
3. **Wait 1-2 s** then verify via [user-orders](user-orders.md).

### Cancel one order by cloid

Same as above but skip the oid lookup:
```bash
python3 examples/06_cancel_order.py cancel-by-cloid <priv_key> <contractId> <cloid>
```
(Not in the example script — action shape below.)

### Cancel all on a contract

1. **Confirming gate required** — this can wipe many orders.
2. Show which orders will be cancelled (list them first via [user-orders](user-orders.md)).
3. **Run**:
   ```bash
   python3 examples/06_cancel_order.py cancel-all <priv_key> <contractId>
   ```

## Action shapes

### cancel — by order id
```json
{"type": "cancel", "cancels": [{"a": 1, "o": 12345}]}
```
Batch multiple:
```json
{"type": "cancel", "cancels": [
  {"a": 1, "o": 12345},
  {"a": 1, "o": 12346},
  {"a": 2, "o": 9999}
]}
```

### cancelByCloid
```json
{"type": "cancelByCloid", "cancels": [{"a": 1, "cloid": "0x000…001"}]}
```

### cancelAll
```json
{"type": "cancelAll", "a": 1}
```

- HTTP 200 (closed-loop, not fire-and-forget).
- Response: `{"limitCancelled": <n>, "conditionalCancelled": <m>}`
- `conditionalCancelled` counts TP/SL entries — see [`../../upside-advanced/references/tpsl.md`](../../upside-advanced/references/tpsl.md).

## Detecting a successful cancel vs. a no-op

For fire-and-forget cancel:

- If the oid didn't exist: `http 202` still returns. It was a no-op.
- If the oid existed: cancel processed asynchronously.

Compare `userOrders` count before/after to know which case you're in.

For `cancelAll`: the response tells you exactly how many were cancelled (closed-loop).

## Templates

### Confirming Response — cancelAll only

Render **verbatim** per [_shared/confirming-response.md](../../upside-onboarding/_shared/confirming-response.md):

```
⚠  About to CANCEL ALL orders on Upside (QA).

  Account:      {aid} — {addr_short}
  Contract:     {contractId} ({symbol_if_known})
  Will cancel:  {n_limit} limit orders + {n_conditional} conditional (TP/SL) orders

  Cancels are reversible only by re-placing.

Reply "yes" to proceed, anything else to cancel.
```

### Cancel Confirmed
```
✓ Cancelled on Upside (QA)

  Account:  {aid}
  Contract: {contractId}
  Cancelled: {oid_list_or_count}
```

### CancelAll result
```
✓ CancelAll executed on Upside (QA)

  Account:              {aid}
  Contract:             {contractId}
  Limit orders removed: {limitCancelled}
  TP/SL removed:        {conditionalCancelled}
```

## Confirming Response

- Cancel single explicit oid: **skip** (safe reversal, user pointed at it).
- `cancelByCloid`: **skip** if user pointed at the cloid, else **confirm**.
- `cancelAll`: **always confirm** — can wipe many orders.

## Rate limit note

Cancels typically process faster than orders. No rate limits on cancel volume have been observed.

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| Cancel `http 202` but order still there | oid didn't match any open order | double-check oid via `userOrders` |
| `errorCode: 30` on cancel signed by agent | agent binding may have been revoked | check `userAgents` |
| `cancelAll` returns `limitCancelled: 0` | nothing was in the book (matching-engine drop before this) | check `userOrders` first |
| `http 400 "unknown action.type: cancelByCloid"` | `cancelByCloid` not available in this environment | fall back to `cancel` with oid |

## See also

- [place-order](place-order.md) — how orders got into the book
- [user-orders](user-orders.md) — verify cancels landed
- [`../../upside-advanced/references/tpsl.md`](../../upside-advanced/references/tpsl.md) — separate `cancelTpSl` for conditional orders
- [_shared/confirming-response.md](../../upside-onboarding/_shared/confirming-response.md) — when to confirm
