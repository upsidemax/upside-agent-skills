---
name: upside-advanced
description: "Upside advanced — agent delegation, TP/SL entries, and error code decoding. Trigger when the user says: run a bot / trading bot / delegate trading / approve agent / revoke agent / API key for bot / grant trading permission / hot wallet / cold wallet / take profit / stop loss / TP/SL / trigger / conditional order / trailing stop / what does errorCode N mean / why was my request rejected / decode error / 代理签名 / 授权机器人 / 止盈 / 止损 / 条件单 / 错误码含义. Requires the account already has a working master key and MO=1 balance."
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

# Upside Advanced

Three related but distinct topics that show up together in practice.

## Intent Routing

Match intent, open one reference. If multiple match (e.g. "my bot got errorCode 30 on a TP/SL"), read them in the order below.

| User Intent | Reference |
| --- | --- |
| grant trading key to a bot / hot key / delegate / approve agent / revoke agent / 授权机器人 / 冷钱包代签 | [agent-delegation](references/agent-delegation.md) |
| stop loss / take profit / TP / SL / trigger / conditional / bracket order / 止盈 / 止损 / 条件单 | [tpsl](references/tpsl.md) |
| errorCode <n> / what does <code> mean / why <error> / decode error / 错误码 <n> / 什么意思 | [error-codes](references/error-codes.md) |
| list my agents / see my bot keys / userAgents / 查代理 | [agent-delegation](references/agent-delegation.md) (list section) |
| my TP triggered but I got errorCode 4 / conditional was untriggered | [tpsl](references/tpsl.md) + [error-codes](references/error-codes.md) |

## Pre-flight

Read [`../upside-onboarding/_shared/preflight.md`](../upside-onboarding/_shared/preflight.md).

Advanced-specific pre-flight, only when the intent is agent delegation:

1. Check the master account has `depositNonce >= 1` (else the master isn't fully registered on chain). Query via `examples/03_check_balance.py <masterAid>`.
2. Confirm the master currently has fewer than 3 named agents (via `userAgents`) if the user plans to add a named one.

## Confirming Response

Agent delegation and TP/SL both mutate account state — go through [`../upside-onboarding/_shared/confirming-response.md`](../upside-onboarding/_shared/confirming-response.md) before every write.

Requires confirmation:
- `approveAgent` — grants trading authority to a key
- `revokeAgent` — kills an existing agent binding
- `tpSl` — creates conditional entries against a position
- `cancelTpSl` — removes them
- `updateLeverage` — changes position risk profile

Does NOT require:
- `userAgents` / `userAccount` / other reads
- Error-code lookup

## Amount Display Rules

Apply [`../upside-onboarding/_shared/amount-display.md`](../upside-onboarding/_shared/amount-display.md). Advanced-specific:

- **Agent addresses**: verbatim, always. Show master and agent addresses side-by-side so the user can't confuse them.
- **TP/SL prices**: same rules as regular order prices. Add "trigger:" prefix when displaying trigger prices to distinguish from limit prices.
- **validUntil**: display as UTC ISO if non-zero; render `0` as "permanent (never expires)".

## Security & Global Notes

Read [`../upside-onboarding/_shared/security.md`](../upside-onboarding/_shared/security.md). Advanced-specific:

- **Agent keys are TRADE-only, but that includes cancelAll**. A compromised agent can drain your open orders (nuisance) but cannot withdraw funds. Still, treat agent private keys as sensitive.
- **`revokeAgent` is irreversible** — once revoked, that agent address is bound to a "revoked" state; you can re-approve, but historical orders under the old binding stay as-is.
- **TP/SL side must be correct**: TP on a long MUST be above current price; SL on a long MUST be below. The backend rejects the wrong side with `errorCode: 1`; always compute and show the correct side to the user before submitting.
- **`updateLeverage` after positions are open**: changes maintenance margin calc for existing positions. Show the before/after in confirmation.

## Failure decoder (quick)

Full table lives in [references/error-codes.md](references/error-codes.md). Fast lookup:

| errorCode | reference row |
|---:|---|
| 1 | validation → check field names & values [error-codes.md](references/error-codes.md#business-errorcode) |
| 4 | unknown contract → [`../upside-trading/references/market-state.md`](../upside-trading/references/market-state.md#boundary-cases) |
| 27, 28, 29 | agent quota / bound to another master / not found → [agent-delegation](references/agent-delegation.md#common-failure-modes) |
| 30 | agent tried non-TRADE → [agent-delegation](references/agent-delegation.md#permission-matrix) |
| 31 | nonce replay/future → [`../upside-onboarding/_shared/signing.md`](../upside-onboarding/_shared/signing.md#nonces) |

## Feature interactions

- Agent + TP/SL: agents CAN sign `tpSl` and `cancelTpSl` (TRADE class). Common pattern: master approves agent for automated trading including TP/SL management.
- Agent + WebSocket: agent's actions appear on `orderUpdates.<masterAddress>`, NOT on the agent's address. Subscribe using master's address.
- Multiple agents: 1 anon + 3 named per master. Named slots overwrite by name.
