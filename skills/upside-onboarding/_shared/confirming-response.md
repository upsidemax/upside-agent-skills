# Confirming Response

> Shared across all Upside skills. Every state-changing action MUST pass through this gate before executing.

State-changing actions on Upside can move funds, create/cancel orders, or grant/revoke permissions. Once submitted they are hard or impossible to reverse. The agent MUST get explicit user confirmation before running the corresponding script.

## When to confirm — ALWAYS

Apply the Confirming pattern before any of these:

| operation | reason |
|---|---|
| `examples/05_place_order.py` | consumes margin, may fill immediately |
| `examples/06_cancel_order.py cancel-all` | can wipe many orders at once |
| `examples/08_agent_delegation.py` (approve or revoke) | grants/removes a private key's trading authority |
| `examples/09_tpsl.py` (place or cancel) | binds/unbinds trigger conditions on a position |
| any `lockCollateral` / `unlockCollateral` | moves funds between margin layers |

## When NOT to confirm — SAFE

Skip the gate for:

- `registerAccount` (idempotent; 2nd call returns 409 accountId)
- All `/info` reads
- WS subscribes
- Cancel a **single** order by explicit `oid` that the user just pointed at

## The confirmation template

Render **verbatim** before running any state-changing script (substitute `{…}` placeholders):

```
⚠  About to {operation summary} on Upside (QA).

  Account:   {accountId} — {address_short}
  Details:   {key details, one per line}

  This action is {reversible|irreversible}. {If irreversible, add: "Once submitted, cannot be undone."}

Reply "yes" to proceed, anything else to cancel.
```

Concrete example — place order:

```
⚠  About to PLACE ORDER on Upside (QA).

  Account:   5 — 0x001cf1…5ec52
  Details:   Contract 1  (BTC-<settle_coin_name>, e.g. BTC-USDC on current QA)
             Side        buy
             Price       100
             Size        1
             Type        Gtc limit
             Reduce-only false

  This action will consume ~100 <settle_coin_name> of margin. Fills are irreversible.

Reply "yes" to proceed, anything else to cancel.
```

## After confirmation

1. User says "yes" (or a clear affirmative) → run the script exactly once. Do not add flags the user didn't approve.
2. User says anything else, or is silent → stop; tell them it was cancelled.
3. Never chain multiple confirmation steps in one turn — one prompt, one action.

## Prohibited

- Never assume "yes" from prior context (a "yes" 3 turns ago doesn't authorize a new order).
- Never batch-run multiple state-changing scripts on a single confirmation.
- Never pass `--force` or equivalent bypass flags on the first invocation. Only after the user has seen the confirmation prompt and typed yes.
- Never show a "sample" that will actually execute. If you're demonstrating the shape of an action, do it in a code block, not a `Bash` tool call.
