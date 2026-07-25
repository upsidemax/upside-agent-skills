# Auto-Airdrop

QA auto-mints the chain's settle coin (currently **10,000 USDC** on QA; the amount and coin are chain-configurable and have changed over time) to every newly registered account, typically within 10-30 seconds. **Always detect the actual amount and coin via `/info configs` + `userAccount`** rather than hardcoding — never assume a fixed figure.

Occasionally misses — this file covers detection + recovery.

## Workflow

1. **After a successful `registerAccount`**, start polling. Interval: 3 s. Timeout: 45 s.
2. **On each poll, run:**
   ```bash
   python3 examples/02_wait_airdrop.py <aid>
   ```
   Or inline via `common.get_balance(aid)` — returns `(mo0_raw, mo1_raw)`.
3. **Success condition**: `depositNonce >= 1` on either layer, OR any positive balance.
4. **Timeout condition**: 45 s elapsed AND `depositNonce == 0` in both layers → miss. Recover per [Miss recovery](#miss-recovery).
5. **Render the Airdrop Result template** to the user.

## Detecting arrival

`depositNonce` is the primary signal:

```python
def airdrop_arrived(aid):
    r = info({"type":"userAccount","accountId":aid,"marketDeployerId":0})
    return int(r.get("depositNonce", "0")) > 0
```

`depositNonce` increments on every deposit event. Fresh accounts have `0`; airdrop bumps to `1`.

## Where the money lands

Non-deterministic — one of:

| layer | field | tradeable? | needs to trade |
|---|---|:---:|---|
| **mo=0** (DexLedger) | `chainBalances` | ❌ | `enrollUserToMarketOwner` + `lockCollateral` to move into MO=1 |
| **MO=1** (Market #1) | `crossCollaterals` | ✅ | nothing further — already margin |

Both count as airdrop success. Only MO=1 balance can back an order. If the airdrop lands in mo=0, migrate:

```json
{"type": "enrollUserToMarketOwner", "marketDeployerId": 1}
{"type": "lockCollateral", "marketDeployerId": 1, "coinId": 1, "amount": "1000000000000"}
```

Both signed by the account owner.

## Observed timing

Sample of 5 successful arrivals:

| aid | arrival time |
|---|---|
| A | 10.4 s |
| B | 10.9 s |
| C | 15.7 s |
| D | 21.7 s |
| E | 22.0 s |

Mean ≈ 16 s. Safe to poll for 45 s, then declare miss.

## Miss recovery

Roughly 25-30% of registrations don't receive an airdrop within 60 s. No retry mechanism attached to a given registration — the miss is per-registration.

**Simplest recovery**: register a fresh wallet. Airdrop misses tend to be per-registration, so a new wallet usually gets one.

```bash
python3 examples/01_register.py         # new wallet + new registration
python3 examples/02_wait_airdrop.py <new_aid>
```

If multiple fresh registrations in a row all miss, the airdrop service is likely down — try again later.

## Template — Airdrop Result

Success:
```
✓ Airdrop received on Upside (QA)

  Account ID:   {aid}
  Landed at:    {t}s after registration
  Location:     {mo=0 DexLedger | MO=1 margin}
  Amount:       {usdt_formatted}
  Next step:    {if mo=0: "Move to MO=1 via lockCollateral before trading" | "Ready to trade"}
```

Miss:
```
⚠  No airdrop after 45 s — occasional per-registration miss on QA.

  Simplest recovery: register a fresh wallet.
    python3 examples/01_register.py
    python3 examples/02_wait_airdrop.py <new_aid>

  If several fresh registrations in a row all miss, the airdrop service is
  likely temporarily down — try again in a few minutes.

  Account ID:   {aid}
  Address:      {addr}
```

## Confirming Response

Polling / checking balance is read-only — **skip** the Confirming gate.

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| `depositNonce = 0` after 45 s | airdrop service miss for this specific registration | register a fresh wallet |
| Balance appears in mo=0 but user wants to trade | airdrop landed on DexLedger layer | run `enrollUserToMarketOwner` + `lockCollateral` |
| `enrollUserToMarketOwner` fails | account not registered, or MO doesn't exist | verify `registerAccount` succeeded; check target `marketDeployerId` exists |

## See also

- [register](register.md) — the registration flow that precedes airdrop
- [query-account](query-account.md) — full balance verification schema
- [_shared/preflight.md](../_shared/preflight.md) — session pre-checks
- [_shared/confirming-response.md](../_shared/confirming-response.md) — confirm gate for state-changing actions
