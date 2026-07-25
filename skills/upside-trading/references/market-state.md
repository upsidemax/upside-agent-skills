# Market State

Point-in-time price + funding info for one contract, plus order book depth.

## Workflow

1. **Identify the contract**. If the user names a symbol (e.g. "BTC"), map to `contractId` via `/info configs.contracts[]` — do NOT hardcode a mapping. On current QA: `1=BTC-USDC, 2=ETH-USDC, 3=SOL-USDC`. Older QA had `BTC-USDT`. `examples/11_show_configs.py` prints the full list.
2. **Query marketState first** (cheap, single fetch):
   ```bash
   python3 examples/04_market_info.py <contractId>
   ```
3. **Check `priceReady`**:
   - `true` → oracle is pushing; orders will match. Proceed.
   - `false` → matching engine will silently drop orders. Warn user; ask whether to proceed.
4. **For depth**, also read `l2Book` (returned by the same script).
5. **Render the Market Snapshot template**.

## marketState query

```json
{"type":"marketState", "asset":"1"}
```

`asset` MUST be a **string** containing the contractId. Integer or missing → `http 400 "missing or invalid asset"`.

## marketState response

```json
{
  "type": "marketState",
  "asset": "1",
  "markPx":       "800",              // mark price (raw, divide by priceScale for display)
  "oraclePx":     "800",              // oracle-aggregated index price
  "lastPx":       "800",              // last traded price
  "priceReady":   true,               // false → matching engine drops orders
  "fundingIndex": "42000",            // cumulative funding
  "fundingLastTimestamp": 1784510817898
}
```

## priceReady semantics

| value | meaning | trade behavior |
|:---:|---|---|
| `true` | oracle is actively pushing prices | orders that pass price-band validation will match |
| `false` | no oracle price for this contract yet | orders receive `http 202` but matching engine silently drops (price band check fails against markPx=0) |

`priceReady: false` is common on a freshly-listed contract before the first oracle push arrives. Not a bug; just wait, or use a contract that's already ready.

## Boundary cases

### Unknown asset (contract doesn't exist)
```
{"type":"marketState","asset":"9999"}
→ 200 {"markPx":"0","priceReady":false,…}
```
Note: NOT a 404. Backend returns a stub. Distinguish "unknown" from "not-ready" by trying `l2Book`:
```
{"type":"l2Book","asset":"9999"}
→ 200 {"levels":[[],[]], "bookVersion":0, …}
```
`bookVersion: 0` = never had orders → likely unknown contract. `bookVersion > 0` with `priceReady: false` = known contract, oracle just not pushing.

### Missing / invalid asset
```
{"type":"marketState"}                       → http 400 "missing or invalid asset"
{"type":"marketState","asset":"abc"}         → http 400 "missing or invalid asset"
{"type":"marketState","asset":"99999999999"} → http 400 "invalid asset"  (int32 overflow)
```

## l2Book query

```json
{"type":"l2Book", "asset":"1"}
```

Response:
```json
{
  "asset": "1",
  "time": 1784551373479,
  "bookVersion": 1,
  "markPx": "800",
  "oraclePx": "800",
  "levels": [
    [{"px":"799","sz":"10","n":2}, {"px":"798","sz":"5","n":1}],
    [{"px":"801","sz":"3","n":1}, {"px":"802","sz":"8","n":2}]
  ]
}
```

- `levels[0]` = bids (sorted descending by `px`)
- `levels[1]` = asks (sorted ascending by `px`)
- `n` = number of orders at that level
- `sz` = total size at that level

## Template — Market Snapshot

Ready to trade:
```
📊 Market Snapshot — Contract {contractId} ({symbol})

  Mark:        {mark_formatted}
  Index:       {index_formatted}
  Last trade:  {last_formatted}
  Funding:     {funding_index}  (last updated {funding_time})
  Book:        best bid {bid_formatted}  |  best ask {ask_formatted}
  Depth (top 5):
    Bids            Asks
    {bid1}          {ask1}
    {bid2}          {ask2}
    ...
```

Not ready:
```
⚠ Market {contractId} exists but has no oracle price yet

  markPx:      0
  priceReady:  false

  Any order you place will be accepted at HTTP layer (202) but silently dropped
  by the matching engine. Wait for the oracle service to push prices, or ask
  the Upside team when it is expected.

  Do you want to place an order anyway (it will not fill)?
```

## Confirming Response

Read-only. **Skip** the Confirming gate.

## Numeric conversions

Prices are decimal strings scaled by the contract's `priceScale` (usually 2 on QA):

```python
mark_human = float(r["markPx"]) / 10**price_scale
```

For contract-specific `priceScale`, query `contractSettings` (returned inside `userAccount` at MO≥1) or ask the Upside team. QA defaults to 2 for all three current contracts.

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| Response looks empty (`markPx:"0"`, `priceReady:false`) | oracle not pushing yet | not fixable client-side; wait or use a different contract |
| Response is HTML | nginx SPA fallback — hit the front-end domain not the API | check the URL; see [_shared/endpoints.md](../../upside-onboarding/_shared/endpoints.md) |
| `http 400 "missing or invalid asset"` | passed int instead of string | wrap `asset` as `str(contract_id)` |

## See also

- [place-order](place-order.md) — needs `priceReady: true` to actually fill
- [user-orders](user-orders.md) — after placing, verify entry in book
- [`../../upside-websocket/references/channels.md`](../../upside-websocket/references/channels.md) — for continuous updates via WS
