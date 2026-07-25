# Error Codes

Two distinct error surfaces to know about:

1. **HTTP status code** — from the envelope / parse layer, or from nginx
2. **`response.data.errorCode`** — a numeric field inside a `http 200` body, set by the business logic

Both can carry `errorMessage`. HTTP messages are consistent; `errorMessage` in `data` is often truncated at 40 chars on QA.

## Workflow

1. **Find the numeric code** in the user's response body.
2. **Look it up below** — HTTP first (400/401/etc), then business `errorCode` (1/27/28/…).
3. **Render the Error Decode template** to the user with the specific fix.
4. If the numeric code is not in either table, gather the full response and check the linked reference for the action.

## HTTP status codes

| status | what it means | typical `code` | typical `message` |
|---:|---|---|---|
| **200** | closed-loop success. Look at `response.data.errorCode` for business result. | `-` | `-` |
| **202** | fire-and-forget accepted. Matching/mint/async work still pending. Check state via `/info`. | `-` | `-` |
| **400** | request malformed at parse layer | `BAD_REQUEST` | `inviteCode required` / `unknown action.type: X` / `missing or invalid marketDeployerId` / `invalid asset` |
| **401** | signature check failed | `SIGNATURE_INVALID` | `recovered address 0x… does not match action.address 0x…` |
| **409** | conflict — resource already exists | `ACCOUNT_ALREADY_EXISTS` | `address already registered: accountId=N` |
| **504** | downstream backend timeout | `DOWNSTREAM_TIMEOUT` | `no response within 2000ms` |
| **503** | node unavailable | — | `no available server` |

Nginx-layer errors (before backend logic) return **HTML**, not JSON. Common one: `405 Not Allowed` on POST to `/info` when the domain's nginx is missing a `location /info` proxy_pass.

## Business `errorCode`

Numeric field inside `response.data`. `0` or missing = no error. Non-zero:

| code | canonical message | typical cause | fix |
|---:|---|---|---|
| **1** | `invalid <field>` / `invalid validUntil (must be 0 or > blo…)` / `invalid ownerAccountId` | generic validation | rename/adjust the offending field |
| **4** | `unknown contract` | `a` references a contractId that doesn't exist | verify via [`../../upside-trading/references/market-state.md`](../../upside-trading/references/market-state.md#unknown-asset) |
| **27** | `agent address bound to another master` | trying to approve an already-bound agent | revoke first, or use a different agent |
| **28** | `named agent quota (3) exceeded` | 4th distinct named agent | revoke one, or reuse an existing name |
| **29** | `agent not found for this account` | `revokeAgent` targeting non-bound agent | verify with `userAgents` |
| **30** | `agent may sign trade actions only` | agent signed FUND or GOV action | sign with master's key |
| **31** | `nonce already used` \| `nonce too far in the future` | replay protection | regenerate the envelope |

## Truncated error messages

QA truncates `data.errorMessage` at 40 characters. Common truncated strings:

- `"invalid validUntil (must be 0 or > blo…"` — full: `"…block-height-derived cutoff)"`
- `"ownerAccountId not registered (account …"` — full: `"…N: never deposited)"`
- `"agent address bound to another master"` — full form

Truncated messages are often enough context. If not, the numeric `errorCode` is authoritative.

## Silently-dropped vs explicit-rejection

Fire-and-forget actions (`order`, `cancel`) can be:

- **Accepted** at HTTP layer (`http 202`) BUT
- **Silently dropped** by matching engine (if e.g. `priceReady=false` or price outside band)

If you don't see `errorCode` in the 202 response body, the fire-and-forget was accepted at HTTP but may still have been dropped. To confirm:

- **Orders**: query `userOrders` after 2 s. The oid should appear (unless dropped).
- **Cancels**: query `userOrders` after 2 s. The oid should NOT appear.

## Closed-loop vs fire-and-forget classes

Backend routes actions to two paths:

| class | HTTP | typical actions |
|---|---|---|
| **closed-loop** | 200 with `data.errorCode` = business result | `registerAccount`, `approveAgent`, `revokeAgent`, `cancelAll`, `updateLeverage`, `modify`, `tpSl`, `cancelTpSl`, `enrollUserToMarketOwner`, `lockCollateral`, `unlockCollateral` |
| **fire-and-forget** | 202 with `data = {count: N}` — actual settling is async | `order`, `cancel`, `cancelByCloid` |

Closed-loop optimizes correctness (immediate result); fire-and-forget optimizes latency.

## Template — Error Decode

Render **verbatim**:

```
✗ Error: {short_summary}

  HTTP status:    {http_code}
  Backend code:   {backend_code_or_-}
  errorCode:      {errorCode_or_-}
  Message:        {message_or_-}

  Cause:          {plain_english_cause}
  Fix:            {specific_action_to_take}

  See:            {link_to_relevant_reference}
```

Example (real errorCode 30):
```
✗ Error: Agent tried to sign a restricted action

  HTTP status:    200
  Backend code:   -
  errorCode:      30
  Message:        agent may sign trade actions only

  Cause:          The signer is a registered agent (bot key), but the action
                  is FUND (deposit/withdraw) or GOV (approve/revoke). Agents
                  only have TRADE authority.
  Fix:            Sign this action with the master's key instead.

  See:            skills/upside-advanced/references/agent-delegation.md#permission-matrix
```

## Confirming Response

Read-only. **Skip** the Confirming gate.

## Common failure modes

Not applicable — this file IS the failure decoder.

## See also

- [agent-delegation](agent-delegation.md) — errorCode 27/28/29/30
- [tpsl](tpsl.md) — errorCode 1 on trigger prices
- [`../../upside-onboarding/_shared/signing.md`](../../upside-onboarding/_shared/signing.md) — errorCode 31 nonce issues
- [`../../upside-trading/references/market-state.md`](../../upside-trading/references/market-state.md) — errorCode 4 unknown contract
- [`../../upside-onboarding/references/query-account.md`](../../upside-onboarding/references/query-account.md) — account fields including `marketDeployerId`
