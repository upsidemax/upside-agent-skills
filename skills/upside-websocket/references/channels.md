# Channels

Per-channel parameter matrix and subscribe examples. For payload shapes, see [payload-samples](payload-samples.md).

## Workflow

1. **Identify the intent** — which channel matches (see table below).
2. **Look up required params** for that channel.
3. **Send subscribe frame** with those params exactly. Wrong param name → `BAD_SUBSCRIPTION`.
4. **Wait for `subscriptionResponse` ACK**.
5. **Consume data** on `channel: "<type>"`.

## Channel matrix

| type | required params | data | typical volume |
|---|---|---|---|
| `l2Book` | `asset` (contractId as string) | full order book snapshot + deltas | high (per contract) |
| `bbo` | `asset` | best bid / offer changes only | medium |
| `trades` | `asset` | executed trades | medium |
| `candle` | `asset`, `interval` (`1m`/`5m`/`15m`/`30m`/`1h`/`4h`/`1d`) | OHLCV bar updates + close | low (1/interval) |
| `config` | *(none)* | global config events (coin created, fee updated) | very low |
| `orderUpdates` | `user` (0x address) | account-scoped order lifecycle | scales with user activity |

**Not supported (as of 2026-07)**: `allMids`, `webData2`, `fills.<address>`. Subscribing returns `BAD_SUBSCRIPTION`.

## `asset` parameter — critical

For every channel that takes a market ID, the param is `asset` — a **string** containing the `contractId`. NOT `coin`, NOT `contractId`, NOT `id`.

```json
✓ {"type":"l2Book", "asset":"1"}
✗ {"type":"l2Book", "coin":"1"}
✗ {"type":"l2Book", "contractId":1}
```

Wrong name → `{"channel":"error","data":{"code":"BAD_SUBSCRIPTION","message":"missing/invalid params for type=l2Book"}}`.

## Subscribe examples

Order book for contract 1:
```bash
python3 examples/07_ws_subscribe.py l2Book --asset 1 --duration 30
```

Trades on contract 1 for 60 s:
```bash
python3 examples/07_ws_subscribe.py trades --asset 1 --duration 60
```

1-minute candles:
```bash
python3 examples/07_ws_subscribe.py candle --asset 1 --interval 1m --duration 120
```

Global config events (very low volume):
```bash
python3 examples/07_ws_subscribe.py config --duration 30
```

Order updates for a specific address:
```bash
python3 examples/07_ws_subscribe.py orderUpdates --address 0xabc… --duration 60
```

## Payload shapes

See [payload-samples](payload-samples.md) for real captured messages.

Key fields per channel:

- **l2Book**: `{asset, time, bookVersion, markPx, oraclePx, levels: [bids, asks]}`
- **bbo**: `{asset, time, bid:{px,sz}, ask:{px,sz}}`
- **trades**: `[{asset, side, px, sz, time, tid}]`
- **candle**: `{asset, interval, openTime, closeTime, open, high, low, close, volume}`
- **config**: `{eventType, ...event-specific}`
- **orderUpdates**: `[{oid, cloid, asset, side, px, sz, st, isConditional, …}]`

## Template — Data Line (for streaming to terminal)

Compact one-liner per message, for the user to watch scroll:

l2Book delta:
```
[l2Book asset=1 v={bookVersion}] bid {best_bid_formatted} @ {best_bid_sz}  |  ask {best_ask_formatted} @ {best_ask_sz}
```

Trade:
```
[trade asset=1] {side} {sz} @ {px} tid={tid}
```

Order update:
```
[order oid={oid} {side}] {status}  {px_formatted} × {sz_formatted}  cloid={cloid_short}
```

## Multiple subscriptions

You can subscribe to many channels on one WS connection. Send multiple subscribe frames (each gets its own ACK). Server routes to different `channel:` values.

Cost: one WS backpressure buffer per connection. If any channel is high-volume (l2Book on busy contract), consider a dedicated connection.

## Confirming Response

Read-only. **Skip** the Confirming gate.

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| `BAD_SUBSCRIPTION missing/invalid params for type=X` | wrong param name | use `asset` |
| `BAD_SUBSCRIPTION unknown subscription type: allMids` | channel not supported | use `l2Book` per-contract instead |
| Subscribed OK, ACK received, no data | correct — some channels (config) are low-volume | wait, or verify with a high-volume channel first |
| `orderUpdates` returns nothing for a fresh address | address has never placed orders | expected |

## See also

- [websocket-protocol](websocket-protocol.md) — envelope + ACK format
- [payload-samples](payload-samples.md) — captured message examples
- [`../../upside-trading/references/place-order.md`](../../upside-trading/references/place-order.md) — REST equivalent for reading userOrders
