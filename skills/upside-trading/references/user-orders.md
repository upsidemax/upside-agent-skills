# User Orders

List orders (open + recent history) for one account.

## Workflow

1. **Query**:
   ```bash
   python3 examples/06_cancel_order.py list <aid>
   ```
   Or inline: `info({"type":"userOrders","accountId":aid,"marketDeployerId":1,"contractId":0})`.
2. **Filter** by status / contract / conditional as needed.
3. **Render** the Order List template.

## Query

```json
{
  "type": "userOrders",
  "accountId": "5",
  "marketDeployerId": 1,       // market deployer id
  "contractId": 0              // 0 = all contracts under this MO
}
```

Filters:
- `contractId: 0` → all contracts (recommended default).
- `contractId: <n>` → only orders on that contract.

## Response

```json
{
  "type": "userOrders",
  "orders": [
    {
      "id": "12345",
      "accountId": "5",
      "marketDeployerId": 1,
      "contractId": 1,
      "marketId": 1,
      "orderSide": "B",
      "orderType": "L",
      "marginMode": "C",
      "positionSide": "OneWay",
      "price": "100",
      "size": "1",
      "reduceOnly": false,
      "cloid": "0x000…001",
      "isConditional": false,
      "status": "Open",
      "parentOrderId": "0"
    }
  ]
}
```

## Field decoder

| field | values | meaning |
|---|---|---|
| `id` | string int | backend order id (aka `oid`); use with `cancel` |
| `orderSide` | `B` \| `S` | Buy or Sell |
| `orderType` | `L` \| `TPM` \| `SLM` \| ... | L = limit; TPM = take-profit market; SLM = stop-loss market |
| `marginMode` | `C` \| `I` | Cross or Isolated |
| `positionSide` | `OneWay` \| `Long` \| `Short` | OneWay = single net position; hedge mode splits |
| `isConditional` | bool | true for TP/SL entries |
| `status` | `Open` \| `Filled` \| `PartiallyFilled` \| `Canceled` \| `Untriggered` \| `Triggered` | lifecycle state |
| `parentOrderId` | string int | non-zero for child orders (rare) |

## Filter recipes

Only open orders:
```python
opens = [o for o in r["orders"] if o["status"] == "Open"]
```

Only TP/SL entries (handle both field names for backend compat):
```python
def is_conditional(o):
    return o.get("isConditional") is True or o.get("cond") is True

tpsl = [o for o in r["orders"] if is_conditional(o)]
```

Order-ids only:
```python
oids = [int(o["id"]) for o in r["orders"]]
```

## Template — Order List

Populated:
```
📋 Open Orders — Account {aid} (Upside QA)

  ID       Contract  Side  Price          Size    Status    cloid
  ─────────────────────────────────────────────────────────────────
  12345    1         BUY   {p_formatted}  {s_fmt} Open      {cloid_short}
  12346    1         SELL  {p_formatted}  {s_fmt} Open      {cloid_short}
  ...

  {n_conditional} conditional (TP/SL) orders included above.
  {n_open} open, {n_filled} filled, {n_cancelled} cancelled.

  Cancel one:   python3 examples/06_cancel_order.py cancel <priv> <contractId> <id>
  Cancel all:   python3 examples/06_cancel_order.py cancel-all <priv> <contractId>
```

Empty:
```
No open orders for account {aid}.
```

## Confirming Response

Read-only. **Skip** the Confirming gate.

## Empty response

`userOrders` on an unknown accountId returns `{"orders": []}` — not an error. Distinguish from "known account with no orders" via `userAccount.depositNonce`:

- `depositNonce = 0`: probably unregistered → run [register](../../upside-onboarding/references/register.md)
- `depositNonce ≥ 1`: registered but no orders yet

## Related — positions vs orders

- `userAccount.positions` = filled inventory (net exposure)
- `userOrders` = queued intent (may become positions)

Don't conflate. The user's "position" is not their "open order".

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| Empty `orders` after placing | matching engine dropped the order | see [place-order](place-order.md#when-the-matching-engine-silently-drops-your-order) |
| `http 400 "missing or invalid marketDeployerId"` | `marketDeployerId` missing or invalid | pass a valid `marketDeployerId` |
| Order shows `status: "Canceled"` after cancel | expected; cancels leave a tombstone | filter by `status == "Open"` when the user asks for "active" |

## See also

- [place-order](place-order.md) — how orders enter the list
- [cancel-order](cancel-order.md) — how they leave
- [`../../upside-onboarding/references/query-account.md`](../../upside-onboarding/references/query-account.md) — positions live in `userAccount`
