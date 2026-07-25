# Payload Samples

Real messages captured from `wss://dev.upsidemax.xyz/ws`. Field names & shapes current as of 2026-07-22.

## Workflow

1. Look up the channel type you subscribed to.
2. Match your received payload against the samples below.
3. Some fields have both a **preferred** and a **legacy** form — handle both for compatibility.

## Subscribe ACK

```json
{"channel":"subscriptionResponse","data":{"method":"subscribe","subscription":{"type":"l2Book","asset":"1"}}}
```

Sent immediately after your subscribe frame. Not data — just an acknowledgement.

## Subscribe error

```json
{"channel":"error","data":{"code":"BAD_SUBSCRIPTION","message":"missing/invalid params for type=l2Book"}}
```

## l2Book snapshot — empty book

Fresh chain, no orders:
```json
{
  "channel": "l2Book",
  "data": {
    "asset": "1",
    "time": 1784551373479,
    "bookVersion": 1,
    "markPx": "0",
    "oraclePx": "0",
    "levels": [ [], [] ]
  }
}
```

## l2Book snapshot — with orders

```json
{
  "channel": "l2Book",
  "data": {
    "asset": "1",
    "time": 1784560000000,
    "bookVersion": 15,
    "markPx": "800",
    "oraclePx": "800",
    "levels": [
      [{"px":"799","sz":"10","n":2}, {"px":"798","sz":"5","n":1}],
      [{"px":"801","sz":"3","n":1}, {"px":"802","sz":"8","n":2}]
    ]
  }
}
```

- `levels[0]` = bids (sorted **descending** by `px`)
- `levels[1]` = asks (sorted **ascending** by `px`)
- `n` = number of orders at that level
- `sz` = total size at that level

## trades

```json
{
  "channel": "trades",
  "data": [
    {"asset":"1", "side":"B", "px":"800", "sz":"1", "time":1784560000000, "tid":42}
  ]
}
```

`side` values: `B` (buy taker) / `S` (sell taker). `tid` monotonically increases per contract.

## candle

```json
{
  "channel": "candle",
  "data": {
    "asset": "1",
    "interval": "1m",
    "openTime":  1784560020000,
    "closeTime": 1784560080000,
    "open":  "800",
    "high":  "801",
    "low":   "799",
    "close": "800",
    "volume":"12"
  }
}
```

Server may emit an "in-progress" update as the current bar evolves, then a "final" version at close. Both are on the same `channel:"candle"`. Distinguish by `time == closeTime` (final) vs `time < closeTime` (in-progress).

## orderUpdates — order created

```json
{
  "channel": "orderUpdates",
  "data": [
    {
      "oid": 12345,
      "cloid": "0x000…001",
      "asset": "1",
      "side": "B",
      "px": "100",
      "sz": "1",
      "st": "Open",
      "isConditional": false,
      "time": 1784560000000
    }
  ]
}
```

## orderUpdates — TP created (conditional)

```json
{
  "channel": "orderUpdates",
  "data": [
    {
      "oid": 12346,
      "asset": "1",
      "side": "S",
      "px": "0",
      "sz": "0",
      "st": "Untriggered",
      "isConditional": true,
      "tp": "1500",
      "tpt": 0
    }
  ]
}
```

**Legacy alias**: this field may appear as `cond: true` instead of `isConditional: true`. Handle both:

```python
def is_conditional(entry):
    return entry.get("isConditional") is True or entry.get("cond") is True
```

## orderUpdates — fill (partial)

```json
{
  "channel": "orderUpdates",
  "data": [
    {
      "oid": 12345,
      "asset": "1",
      "side": "B",
      "px": "100",
      "sz": "0.5",         // remaining size
      "st": "PartiallyFilled",
      "fillPx": "100",
      "fillSz": "0.5",
      "time": 1784561000000
    }
  ]
}
```

## orderUpdates — rejected

When the matching engine rejects an order (bad contract, insufficient margin,
position-mode mismatch, etc.) it pushes a `st:"Rejected"` entry. A rejected order
**appears only here** — it gets no order id, never lands in `openOrders`, and no
order-id / cloid query can find it.

```json
{
  "channel": "orderUpdates",
  "data": [
    {"id":"-1","n":"1743600000000","r":"144115188075856500","a":"5","c":1,"code":19,"reason":"account not enrolled","st":"Rejected"}
  ]
}
```

- `id` is always `"-1"`. Correlate on **`n`** (the nonce you signed, echoed back),
  or on `cid` if you sent a client order id — **not** on `r` (server-assigned
  requestId, unknown at submit time).
- `code` / `reason` explain the rejection (`reason` ≤ 40 chars). No `b`/`t`/`p`/`s`
  (the order never existed).

## config — coin created

```json
{
  "channel": "config",
  "data": {
    "eventType": "CoinCreated",
    "coinId": 5,
    "name": "XYZ",
    "szDecimals": 8,
    "isMargin": 0
  }
}
```

## config — fee update

```json
{
  "channel": "config",
  "data": {
    "eventType": "ConfigChanged",
    "field": "takerBps",
    "before": 5,
    "after": 6,
    "marketDeployerId": 1,
    "contractId": 1
  }
}
```

## Status vocabulary (`st` field)

| value | meaning |
|---|---|
| `Open` | rests on book |
| `PartiallyFilled` | some quantity filled |
| `Filled` | fully filled |
| `Canceled` | user or system cancelled |
| `Untriggered` | conditional (TP/SL) waiting for trigger price |
| `Triggered` | conditional was hit; matching engine is executing the market close |
| `Rejected` | rare; e.g. price outside band at match time |

## Confirming Response

Read-only. **Skip** the Confirming gate.

## See also

- [websocket-protocol](websocket-protocol.md) — envelope format
- [channels](channels.md) — how to subscribe to each of these
- [`../../upside-advanced/references/tpsl.md`](../../upside-advanced/references/tpsl.md) — TP/SL semantics
