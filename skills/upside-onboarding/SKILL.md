---
name: upside-onboarding
description: "Upside first-time onboarding — the single skill for creating an account, receiving test funds, and verifying balance. Trigger when the user says: register / sign up / create account / new account / I want to trade / I have no account yet / how do I start / open an account / get test funds / claim airdrop / where's my balance / why is my balance zero / testnet funds / QA funds / check my USDT / show my balance / verify my funds / airdrop timing / alpha test invitation code / invite code / invitation code / 邀请码 / 注册账户 / 领取空投 / 测试资金 / 我要交易 / 我的余额 / 查余额. Prerequisite skill for upside-trading."
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

# Upside Onboarding

First-time flow: wallet generation → registration (with alpha test invitation code) → auto-airdrop → balance verification. Runs entirely on the QA environment `https://dev.upsidemax.xyz`.

## Intent Routing

Match the user's intent to a row and **open that row's linked file first** — it holds the full flow. Don't load other rows. Each reference lists its own follow-on files at the bottom.

| User Intent | Reference |
| --- | --- |
| register / create account / sign up / new account / 注册 / 开户 | [register](references/register.md) |
| wait for airdrop / claim airdrop / test funds / where's my USDT / where's my USDC / 空投 / 领币 | [auto-airdrop](references/auto-airdrop.md) |
| check balance / show my funds / verify balance / 查余额 / 我有多少 USDT / 我有多少 USDC | [query-account](references/query-account.md) |
| what's the settle coin / USDT or USDC / what contracts exist / list coins / 结算币是啥 / 有哪些合约 | [configs](references/configs.md) |
| I want to trade but have no account / start from zero / 从零开始 | run register → auto-airdrop → query-account (settle coin auto-detected via configs) |

## Pre-flight

Before the first command each session, read and follow [_shared/preflight.md](_shared/preflight.md). It verifies deps and QA reachability; skip only if the user has already run something successfully this session.

## Endpoints & signing

- Endpoints (QA): [_shared/endpoints.md](_shared/endpoints.md)
- Envelope signing protocol (EIP-712): [_shared/signing.md](_shared/signing.md)

Every write is signed by the wallet's own key. Wrong signature = HTTP 401. See signing.md.

## Confirming Response

`registerAccount` is idempotent and safe — **skip** the Confirming gate. Any downstream state-change (order, agent grant, lockCollateral) goes through [_shared/confirming-response.md](_shared/confirming-response.md).

## Security & Global Notes

Read [_shared/security.md](_shared/security.md) once at session start. Onboarding-specific rules:

- **Never** ask the user to paste a private key into chat — tell them to run `python3 examples/01_register.py` locally.
- **Do** echo the private key ONLY when the script itself just generated it and the user is watching (QA-only). Never reproduce it from earlier in the transcript.
- **Never** treat `depositNonce = 0` as "no account" — it just means "no funds yet". Distinguish by attempting `registerAccount` (returns 409 for existing).

## Amount Display Rules

Follow [_shared/amount-display.md](_shared/amount-display.md). Quick reference:

- **Never hardcode `USDT`** — the chain can initialize with either USDC or USDT, depending on its configuration. Auto-detect via [`references/configs.md`](references/configs.md) → `common.get_settle_coin()`.
- Settle-coin amounts: divide raw by `10**szDecimals` (both USDC and USDT are 6), show as `1,000,000.00 USDC` (or whichever the chain declared).
- Addresses: verbatim only.
- accountId: bare integer (`aid=5`).

## Three common mistakes to avoid

1. **`inviteCode` goes at envelope level**, not inside `action`. Wrong placement returns `inviteCode required`. See [_shared/signing.md](_shared/signing.md#envelope-shape).
2. **Balance queries use `marketDeployerId`**. See [references/query-account.md](references/query-account.md#the-marketdeployerid-field).
3. **Airdrop lands in one of two layers** (mo=0 or MO=1). Both count as success. Only MO=1 can trade — use `enrollUserToMarketOwner` + `lockCollateral` to migrate mo=0 → MO=1. See [references/auto-airdrop.md](references/auto-airdrop.md#where-the-money-lands).

## Once done

When the user has `depositNonce ≥ 1` AND `MO=1 crossCollateral > 0`, they're ready to trade. Route to [`../upside-trading/SKILL.md`](../upside-trading/SKILL.md).
