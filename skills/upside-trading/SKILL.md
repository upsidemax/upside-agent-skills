---
name: upside-trading
description: "Upside trading — the single skill for market data, order placement, order management, and cancellation. Trigger when the user says: buy X / sell X / place order / limit order / market order / IOC / GTC / post-only / cancel order / cancel all / modify order / change my order / what's the price of / show BTC price / order book / bid / ask / market state / my open orders / my orders / what orders do I have / update leverage / change leverage / 下单 / 挂单 / 撤单 / 取消订单 / 查订单 / 行情 / 盘口 / 修改订单 / 改杠杆. Requires an account with MO=1 balance — run upside-onboarding first."
license: MIT
metadata:
  author: upside-agent-skills
  version: "0.2.0"
  homepage: "https://dev.upsidemax.xyz"
  agent:
    requires:
      python: ">=3.9"
      packages: ["eth-account", "eth-keys", "eth-utils", "eth-hash[pycryptodome]", "requests"]
    install:
      - id: pip
        kind: python
        packages: ["eth-account", "eth-keys", "eth-utils", "eth-hash[pycryptodome]", "requests"]
        label: "Install Python dependencies"
---

# Upside Trading

Query market state, place/cancel/modify orders on the Upside QA environment. Assumes the user already has MO=1 balance (see [`../upside-onboarding/SKILL.md`](../upside-onboarding/SKILL.md) if not).

## Intent Routing

Match the intent, open **one** reference, execute its Workflow. Never guess field names or values not documented in the linked file.

| User Intent | Reference |
| --- | --- |
| what's the price / show market / mark price / index price / oracle price / 行情 | [market-state](references/market-state.md) |
| order book / bids / asks / depth / 盘口 / 挂单深度 | [market-state](references/market-state.md) (l2Book section) |
| place order / buy / sell / limit / IOC / GTC / market / 下单 / 挂单 | [place-order](references/place-order.md) |
| modify order / change price/size / 修改订单 | [place-order](references/place-order.md) (modify section) |
| cancel one order / cancel by cloid / 撤单 | [cancel-order](references/cancel-order.md) |
| cancel all / cancel every order on a contract / 一键撤 | [cancel-order](references/cancel-order.md) (cancelAll section) |
| show my open orders / list orders / 查订单 / 我的订单 | [user-orders](references/user-orders.md) |
| update leverage / change leverage / isolate a position / 改杠杆 | [place-order](references/place-order.md) (updateLeverage section) |

## Pre-flight

Read [`../upside-onboarding/_shared/preflight.md`](../upside-onboarding/_shared/preflight.md) once per session. Then, before placing any order, run these two checks:

1. `python3 examples/04_market_info.py <contractId>` — confirm `priceReady: true`. If false, orders will be silently dropped by matching engine; **warn the user** and ask whether to proceed anyway.
2. `python3 examples/03_check_balance.py <accountId>` — confirm MO=1 `marginAvailableForOrder > estimated notional`. If insufficient, do NOT place; suggest either reducing size or running `lockCollateral` from DexLedger.

## Confirming Response

Every state-changing trade action passes through [`../upside-onboarding/_shared/confirming-response.md`](../upside-onboarding/_shared/confirming-response.md). Show the confirmation template BEFORE calling any script.

Requires confirmation:
- `place-order` (any variant)
- `cancel-order cancel-all`
- `place-order` `modify` sub-action
- `updateLeverage`

Does NOT require confirmation:
- All `/info` reads (market-state, l2Book, userOrders)
- Cancel a single order the user just explicitly pointed at (their oid, spelled out)

## Amount Display Rules

Follow [`../upside-onboarding/_shared/amount-display.md`](../upside-onboarding/_shared/amount-display.md). Trading-specific:

- **Prices**: divide by contract's `priceScale` (usually 2). Show 2 decimals for ≥100, 4 for 1-100, 8 for <1.
- **Sizes**: divide by `qtyScale` (usually 4).
- **Notional**: `size * price` for margin estimates before order placement.
- `priceReady: false` → render mark price as `— (no oracle price)`, not "0".

## Security & Global Notes

Read [`../upside-onboarding/_shared/security.md`](../upside-onboarding/_shared/security.md). Trading-specific rules:

- **Never** compute notional in raw units in messages to the user — always convert to human USDT.
- **Never** re-use a cloid across orders — it's an idempotency key.
- **Never** modify an order that has already partially filled without warning the user (their fill is now retroactively at a different average price).
- Before placing a **reduce-only** order (`r: true`), verify the user has a matching position; otherwise the order will be silently dropped.

## Failure decoder

Consolidated table of what to do when the wire returns an error. Details in each row's linked file.

| symptom | likely cause | reference |
|---|---|---|
| `http 202` but `userOrders` count = 0 | `priceReady: false` — engine dropped the order | [market-state](references/market-state.md#priceready-semantics) |
| `errorCode: 30` on order | signer is an agent trying to sign non-TRADE | [`../upside-advanced/references/agent-delegation.md`](../upside-advanced/references/agent-delegation.md#permission-matrix) |
| `http 400 "missing or invalid marketDeployerId"` | `marketDeployerId` missing or invalid | [`../upside-onboarding/references/query-account.md`](../upside-onboarding/references/query-account.md) |
| `errorCode: 4 "unknown contract"` | non-existent contractId | [market-state](references/market-state.md#unknown-asset) |
| `signer 0x… has no registered account` | fresh wallet, never registered | [`../upside-onboarding/SKILL.md`](../upside-onboarding/SKILL.md) |
| Full error code table | any numeric errorCode | [`../upside-advanced/references/error-codes.md`](../upside-advanced/references/error-codes.md) |

## Live data

If the user wants real-time updates instead of polling, route to [`../upside-websocket/SKILL.md`](../upside-websocket/SKILL.md).
