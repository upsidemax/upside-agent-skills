# Configs — chain metadata (settle coin, contract list)

`/info configs` returns the live chain-level metadata: which coins exist, what the settle coin is per market deployer, all contracts and their scale / leverage parameters. **This is the source of truth** — don't hardcode `USDT` / `USDC` / `BTC-USDT` names.

## Workflow

1. **Once per session** (or once per BASE_URL, cached), fetch:
   ```bash
   python3 examples/11_show_configs.py
   ```
   Or programmatically: `common.configs()`.
2. **Look up the settle coin** for the market deployer you're using (usually MD=1):
   ```python
   from common import get_settle_coin
   sc = get_settle_coin(1)          # {'coinId':1,'name':'USDC','szDecimals':6,...}
   ```
3. **Look up a contract** by contractId:
   ```python
   from common import get_contract
   c = get_contract(1)              # {'contractId':1,'name':'BTC-USDC','baseCoinId':3,'quoteCoinId':1,...}
   ```
4. Use `common.format_amount(raw)` for balances — it auto-uses the settle coin's name and szDecimals.

## Query

```json
POST /info { "type": "configs" }
```

Optional filter: `{"type":"configs","marketDeployerId":N}` — trims contracts to that MD only.

## Response shape (abridged)

```json
{
  "type": "configs",
  "coins": [
    {"coinId": 1, "name": "USDC", "szDecimals": 6, "isMargin": true,  "status": "Active"},
    {"coinId": 2, "name": "USDT", "szDecimals": 6, "isMargin": true,  "status": "Active"},
    {"coinId": 3, "name": "BTC",  "szDecimals": 8, "isMargin": false, "status": "Active"},
    …
  ],
  "marketDeployers": [
    {"marketDeployerId": 1, "settleCoinId": 1, "deployerAccountId": "1",
     "liquidatorAccountId": "2", "deployerTakerBps": 5, "deployerMakerBps": 2}
  ],
  "contracts": [
    {"contractId": 1, "name": "BTC-USDC", "baseCoinId": 3, "quoteCoinId": 1,
     "marketDeployerId": 1, "priceScale": 2, "qtyScale": 4,
     "tickSize": "1", "stepSize": "1", "defaultLeverage": "10",
     "maxPositionNotional": "1000000000000", "minTradeNtl": "1",
     "fundingInterval": 3600, "defaultTakerBps": 5, "defaultMakerBps": 2,
     "tiers": [{"upperBound": "…","maxLeverage": "50", "imBps": 100, "mmBps": 50}],
     "status": "Active"},
    …
  ],
  "chainFeeAccountId": "…",
  "chainFeeShareBps": …,
  "allIsMarginCoins": […],
  "shareMarginGroups": […]
}
```

## What you need to know per field

| Field | Meaning |
|---|---|
| `coins[].coinId` | Numeric ID used everywhere in the API (`chainBalances[].coinId`, `lockCollateral.coinId`, etc.) |
| `coins[].name` | Human-readable symbol (`USDC`, `USDT`, `BTC`, …). Never hardcode from your side. |
| `coins[].szDecimals` | Divide raw amounts by `10**szDecimals` to render |
| `coins[].isMargin` | `true` = can be used as collateral (USDC / USDT); `false` = base coin only (BTC / ETH / SOL) |
| `marketDeployers[].settleCoinId` | **The settle coin for this MD** — look up in `coins[]` for name and decimals |
| `contracts[].name` | Contract symbol (`BTC-USDC`). Naming convention: `<base>-<settle>`. The display name is informational — always trust `quoteCoinId` for the settle coin, not the name. |
| `contracts[].baseCoinId` / `quoteCoinId` | Composition. `quoteCoinId` always equals the MD's `settleCoinId` in current deployments. |
| `contracts[].priceScale` / `qtyScale` | Divide raw price / raw size by `10**scale` |
| `contracts[].tickSize` / `stepSize` | Minimum price / size increments (raw units) |

## Caching

`common.configs()` caches the response per BASE_URL. Bust the cache with `configs(force_refresh=True)` after a governance change (rare) or if the chain was re-initialized.

## When configs might mislead

- **Contract display names can lie**: The old `REBATE-USDT` / `TICK10-USDT` / `BUILDER-USDT` contracts on current QA all have `quoteCoinId=1=USDC` despite the `-USDT` suffix — leftovers from a previous naming convention. Always derive settlement from `quoteCoinId` and MD's `settleCoinId`, not the string.
- **`status != "Active"` contracts**: Skip these for trading — they may be paused or delisted.
- **New coin listed mid-session**: `config` WS channel emits `CoinCreated` events; refresh `configs()` on receive.

## See also

- [`../_shared/amount-display.md`](../_shared/amount-display.md) — how to render `raw` amounts with the right name
- [`../../upside-trading/references/market-state.md`](../../upside-trading/references/market-state.md) — per-contract runtime price state (markPx, priceReady, etc.)
- [`query-account.md`](query-account.md) — balance query, uses `chainBalances[].coinId` which you decode via configs
- [`../../../../examples/11_show_configs.py`](../../../examples/11_show_configs.py) — runnable dump
