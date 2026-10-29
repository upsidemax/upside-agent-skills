# Funding

A newly registered account has a **zero balance on every environment** (Mainnet
and Devnet). Nothing is credited automatically — there is no airdrop. Before it can
trade, the account has to be funded, and how depends on the environment:

| Environment | How to fund |
|---|---|
| **Mainnet** | **Deposit** real funds into the account. There is no faucet. |
| **Devnet** | Contact the UpsideMAX team for Devnet funds. |

Do not invent a deposit address, endpoint, or faucet, and do not re-register to
"get funds".

## Workflow

1. **After a successful `registerAccount`**, check the balance once:
   ```bash
   python3 examples/02_check_funding.py [aid]   # default: USER_ACCOUNT_ID from .env
   ```
   Or inline via `common.get_balance(aid)` — returns `(mo0_raw, mo1_raw)`.
2. **Both 0** → stop and render the Not Funded template. Do not poll.
3. **Funds at mo=0 only** → they are not tradeable yet; migrate them (below).
4. **MO=1 > 0** → ready to trade. Route to [`../../upside-trading/SKILL.md`](../../upside-trading/SKILL.md).

## Where funds sit

| layer | field | tradeable? | needs to trade |
|---|---|:---:|---|
| **mo=0** (chain level) | `chainBalances` | ❌ | `enrollUserToMarketOwner` + `lockCollateral` to move into MO=1 |
| **MO=1** (Market #1) | `crossCollaterals` | ✅ | nothing further — already margin |

Only MO=1 balance can back an order. To migrate from mo=0:

```json
{"type": "enrollUserToMarketOwner", "marketDeployerId": 1}
{"type": "lockCollateral", "marketDeployerId": 1, "coinId": 1, "amount": "<raw amount>"}
```

Both signed by the account owner. `lockCollateral` moves funds — confirm first via
[_shared/confirming-response.md](../_shared/confirming-response.md).

## Template — Not Funded

```
⚠  Account {aid} has a zero balance on UpsideMAX ({Mainnet | Devnet}).

  A newly registered account starts empty. Fund it before trading:
    {Mainnet: deposit funds into the account |
     Devnet:  contact the UpsideMAX team for Devnet funds}
  then re-run:
    python3 examples/02_check_funding.py {aid}
```

## Confirming Response

Checking the balance is read-only — **skip** the Confirming gate. `lockCollateral` is not.

## See also

- [register](register.md) — the registration flow that precedes funding
- [query-account](query-account.md) — full balance schema
