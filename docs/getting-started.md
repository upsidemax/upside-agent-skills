# Getting Started

This guide takes you from zero to your first order on UpsideMAX. No prior DEX experience is required.

**Summary** — one command:
```bash
./install.sh && python3 examples/quick_start.py
```
That is the complete flow. Read the sections below to understand each step.

---

## What is UpsideMAX?

A decentralized perpetual futures exchange. You put up a stablecoin (the settle coin — read it from `configs`) as collateral, and you can go long or short on contracts like `BTC-USDC`, `ETH-USDC`, etc. Every action (deposit, order, cancel) is a signed request from a wallet address — no username/password.

**Which coin is the settle coin on this deployment?** Query `/info configs` — see `marketDeployers[0].settleCoinId`, then look up its name in `coins[]`. `examples/11_show_configs.py` prints the full snapshot.

Signing uses **EIP-712** with secp256k1 (same primitives as Ethereum), domain `{name:"Exchange", version:"1", chainId}` — the chainId depends on the environment.

| Environment | Endpoint | chainId | |
|---|---|---|---|
| **Mainnet** (default) | `https://upsidemax.xyz` | `9788` | real funds |
| Devnet | `https://dev.upsidemax.xyz` | `9767` | testing — set `UPSIDE_BASE_URL` |

Registration needs an invitation code on both. A new account starts with a zero balance and must be funded before it can trade.

## Prerequisites

- Python 3.9+ (`python3 --version`)
- `pip` (`python3 -m pip --version`)

That's it. No wallet software, no browser extension.

## Install

```bash
git clone https://github.com/upsidemax/upside-agent-skills.git
cd upside-agent-skills
./install.sh
```

Installs 4 Python packages (`eth-keys`, `eth-utils`, `requests`, `websocket-client`). If `pip` fails, use `python3 -m venv .venv && source .venv/bin/activate && ./install.sh`.

## The 5 concepts you need to know

Understand these before placing an order; they appear throughout the API.

### 1. Wallet address vs accountId

- **Address** is a 42-char hex string like `0xabc…` derived from a private key. Same as an Ethereum address.
- **accountId** (aka `aid`) is a small integer (`5`, `12`, `100`) that the backend assigns when you first register. Once registered, the address and aid map 1:1 forever.

Most API queries use `accountId`, not the address. Register once to get your aid; save it somewhere.

### 2. Two balance layers: mo=0 vs MO=1

Every account has funds in TWO places:

| layer | name | can trade with it? |
|---|---|:---:|
| `mo=0` | **DexLedger** (chain-level ledger) | ❌ |
| `MO=1` | **Market #1** (locked as trading margin) | ✅ |

To move `mo=0 → MO=1`: run `enrollUserToMarketOwner` then `lockCollateral`.

Analogy: `mo=0` is your bank account; `MO=1` is money you've transferred to your broker's margin account.

### 3. Contract vs coin

- **Coin** (`coinId`): a currency. Ids differ per environment — do NOT hardcode; call `/info configs` and read `marketDeployers[0].settleCoinId`.
- **Contract** (`contractId`): a tradeable pair (e.g. `BTC-USDC`). Ids differ per environment; names come from `/info configs.contracts[].name`.

You trade a `contract`. Your P&L settles in the `settleCoin` (whichever the chain declared). Do NOT confuse `coinId` with `contractId` — they're different sequences.

### 4. Master vs Agent

Every account has a **master private key** (full authority: trade, deposit, withdraw, approve agents).

Optionally, the master can approve up to 4 **agent** keys (1 anon + 3 named). Agents can trade under the master's account but **cannot** withdraw or approve more agents. Useful for bot deployments: keep the master offline; put the agent key on a server.

You don't need agents on day one — the master key alone can do everything.

### 5. EIP-712 signing

Every write request (register / order / cancel / etc.) is signed with EIP-712. Two paths, auto-routed by `action.type`:

- **Typed path** for account-level actions (`registerAccount`, `approveAgent`, `revokeAgent`, `lockCollateral`, `unlockCollateral`, `transferBetweenDeployers`) — each has its own typed struct.
- **Agent path** for trading actions (`order`, `cancel`, `modify`, `tpSl`, `updateLeverage`, etc.) — the whole canonical JSON of `action` is folded into a single `actionHash` inside an `Agent(string source,bytes32 actionHash)` wrapper.

Domain: `{name: "Exchange", version: "1", chainId, verifyingContract: 0x0}` — chainId `9788` on Mainnet, `9767` on Devnet, for both paths.

`examples/common.py` handles all of this. You only touch signing directly if you're writing a client in another language — see [../skills/upside-onboarding/_shared/signing.md](../skills/upside-onboarding/_shared/signing.md) for the full spec + reference implementation.

## Step 1: Register your account

```bash
python3 examples/01_register.py
```

Output:
```
→ POST https://upsidemax.xyz/exchange
  address:     0xbc441092113fc1ccb2a6197f095c11e730070fed
  private key: saved to …/.env (USER_PRIVATE_KEY)

✓ registered as accountId=26 (saved as USER_ACCOUNT_ID)
```

The private key is written to the gitignored `.env` (mode 600) and is **never printed** — on Mainnet it controls real funds. Back that file up; the other example scripts pick it up from there.

### Why is there an invitation code?

Registration requires an invitation code on Mainnet and Devnet. Request one from the UpsideMAX team and set it via the `UPSIDE_INVITE_CODE` environment variable. The code is placed at the envelope level (not inside `action`); `common.py` handles this.

## Step 2: Fund your account

A newly registered account has a **zero balance** — nothing is credited automatically, on any environment. Fund it before trading — on **Mainnet**, deposit funds into the account (there is no faucet or airdrop); on **Devnet**, contact the UpsideMAX team for Devnet funds. Then check:

```bash
python3 examples/02_check_funding.py      # uses USER_ACCOUNT_ID from .env
```

It reads the balance once and stops with a clear message if it is still zero. To convert raw amounts: `human = raw / 10**szDecimals` (read `szDecimals` from `configs`).

## Step 3: Check your balance

```bash
python3 examples/03_check_balance.py 26
```

Shows both layers with the actual coin name (auto-detected). If MO=1 has settle-coin balance — ready to trade. If money only shows in mo=0 (DexLedger), you need to migrate:

```python
# One-liner via examples/common.py
from common import send_exchange, require_user_wallet
pk, _, _ = require_user_wallet()          # USER_PRIVATE_KEY from .env
send_exchange(pk, {"type":"enrollUserToMarketOwner","marketDeployerId":1})
send_exchange(pk, {"type":"lockCollateral","marketDeployerId":1,"coinId":1,"amount":"1000000000000"})
```

## Step 4: Look at the market

```bash
python3 examples/04_market_info.py 1
```

Look at `priceReady`:
- `true` → oracle is pushing; orders will actually match.
- `false` → contract exists but no oracle price yet. Orders receive `202 accepted` but silently dropped by matching engine.

If `priceReady: false`, wait, or try a different contract.

## Step 5: Place your first order

```bash
python3 examples/05_place_order.py 1 100 1 buy
```

Arguments:
- (the signing key is read from `.env` — never pass it on the command line)
- `1` — contractId (run `11_show_configs.py` to see all)
- `100` — limit price
- `1` — order size
- `buy` — direction

Response:
```
http 202
body {"status":"accepted","response":{"type":"order","data":{"count":1}}}
```

`http 202 accepted` means the request reached the matching engine. Wait 1-2 seconds, then confirm the order actually landed in the book:

```bash
python3 examples/06_cancel_order.py list 26
```

If you see your order with `status: Open`, you're in the book!

If you see zero orders despite `http 202`, the matching engine silently dropped it. Common causes:
- `priceReady: false` (check step 4)
- Price outside price-band (e.g. price too far from mark)
- Insufficient margin (check step 3)
- Reduce-only order with no matching position

## Step 6: Cancel your order

```bash
python3 examples/06_cancel_order.py cancel 1 <oid>
```

Or nuke all your orders on a contract:
```bash
python3 examples/06_cancel_order.py cancel-all 1
```

## What next

You've done the full loop. From here:

| I want to… | Read |
|---|---|
| Place lots of orders / write a bot | [../skills/upside-trading/references/place-order.md](../skills/upside-trading/references/place-order.md) |
| Watch prices live (not poll) | [../skills/upside-websocket/SKILL.md](../skills/upside-websocket/SKILL.md) |
| Use a separate key for the bot | [../skills/upside-advanced/references/agent-delegation.md](../skills/upside-advanced/references/agent-delegation.md) |
| Attach a stop-loss to my position | [../skills/upside-advanced/references/tpsl.md](../skills/upside-advanced/references/tpsl.md) |
| Understand an error I got | [faq.md](faq.md) or [../skills/upside-advanced/references/error-codes.md](../skills/upside-advanced/references/error-codes.md) |
| Add funds | Mainnet: deposit into the account · Devnet: contact the UpsideMAX team |

## AI-assisted mode

If you're using Claude Code, Cursor, or another AI coding tool, you don't need to read any of the above. Just tell the AI what you want ("I want to try trading on UpsideMAX") and it will follow the skill flow automatically. "Let me try it" starts the one-command test drive (`upside-test`), which runs on **Devnet** by default; the other skills act on Mainnet unless `UPSIDE_BASE_URL` points to Devnet. See [../README.md](../README.md#skill-loading).

## Common first-time issues

Full list in [faq.md](faq.md). The 3 most common:

1. **`inviteCode required`** — you put it inside `action`. It goes at envelope level.
2. **All balance fields are `null`** — you used `marketOwnerId` instead of `marketDeployerId`.
3. **Order returned 202 but doesn't show up** — check `priceReady` on the contract.

## Everything else

- Full concept map: [../README.md](../README.md)
- API-level reference: [../skills/](../skills/)
- Security: [../SECURITY.md](../SECURITY.md)
