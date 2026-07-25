# Register

Create a new account on Upside QA. Idempotent: safe to run twice. Signed by the wallet's own key.

## Workflow

1. **Confirm the user has a private key.** If not, run `python3 examples/01_register.py` (which generates + registers in one shot). If yes, they can invoke `registerAccount` themselves — see step 3.
2. **Include the alpha test invitation code if the gate is on.** Request an alpha test invitation code from the Upside team and set it via the `UPSIDE_INVITE_CODE` environment variable; it is supplied at envelope level as `inviteCode`. Harmless if the gate is off.
3. **Run:**
   ```bash
   python3 examples/01_register.py
   ```
4. **Read the response** using the response-parsing rules below.
5. **Render the Registration Result template** to the user.
6. **Route on outcome:**
   - Fresh account (`http 200`) → suggest `python3 examples/02_wait_airdrop.py <aid>` next.
   - Already registered (`http 409`) → extract `accountId` from the message, route directly to [query-account](query-account.md) or [auto-airdrop](auto-airdrop.md).

## Action & envelope

Action:
```json
{"type": "registerAccount", "address": "0x…lowercase 40 hex…"}
```

Envelope:
```json
{
  "action":     {"type": "registerAccount", "address": "0x…"},
  "signature":  {"r":"0x…","s":"0x…","v":27},
  "nonce":      1784510817898,
  "inviteCode": "<alpha test invitation code>"
}
```

`inviteCode` MUST be at envelope level, not inside `action`. See [_shared/signing.md](../_shared/signing.md#envelope-shape).

## Response cases

### Case A — fresh account
```
http 200
body: {"status":"ok","requestId":"…","response":{"type":"registerAccount","accountId":"6"}}
```
Extract: `aid = body["response"]["accountId"]`.

### Case B — already registered (idempotent)
```
http 409
body: {"status":"error","code":"ACCOUNT_ALREADY_EXISTS","message":"address already registered: accountId=5"}
```
Extract: `aid = message.split("accountId=")[-1].strip()`. Treat as success.

### Case C — no alpha test invitation code
```
http 400
body: {"status":"error","code":"BAD_REQUEST","message":"inviteCode required"}
```
Fix: add the alpha test invitation code as `"inviteCode"` at envelope level (request one from the Upside team and set it via the `UPSIDE_INVITE_CODE` environment variable). Re-run.

### Case D — signer mismatch
```
http 401
body: {"status":"error","code":"SIGNATURE_INVALID","message":"recovered address 0x… does not match action.address 0x…"}
```
Cause: signed with the wrong key. Cannot register on someone else's behalf. If the user provided the address, ask them to sign it with the matching private key.

## Template — Registration Result

Render verbatim (substitute `{…}`):

```
✓ Registered on Upside (QA)

  Account ID:   {aid}
  Address:      {addr}
  Status:       {new | pre-existing}
  Next step:    Wait ~15 seconds for the auto-airdrop of 1,000,000 USDT.
                Or run: python3 examples/02_wait_airdrop.py {aid}
```

For pre-existing accounts:

```
ℹ Account already exists on Upside (QA)

  Account ID:   {aid}
  Address:      {addr}
  Suggestion:   python3 examples/03_check_balance.py {aid}   # see current balance
                python3 examples/02_wait_airdrop.py {aid}    # if you never received airdrop
```

## Field validity

- `address`: lowercase, `0x`-prefixed, exactly 42 chars total. Mixed-case (EIP-55) is unsafe — some backends reject it.
- `inviteCode`: case-sensitive. Enter it exactly as provided by the Upside team.
- `nonce`: millisecond Unix timestamp. Not important which epoch — backend just checks it's not a replay.

## Confirming Response

`registerAccount` is **idempotent and safe** — skip the Confirming gate. See [_shared/confirming-response.md](../_shared/confirming-response.md#when-not-to-confirm--safe).

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| `http 400 inviteCode required` | put `inviteCode` inside `action` | move to envelope level |
| `http 401 SIGNATURE_INVALID` | wrong key signed | use the key that owns `action.address` |
| `http 409 ACCOUNT_ALREADY_EXISTS` | not a failure | parse `accountId=N` from message; proceed |
| No response / timeout | QA unreachable | retry shortly; if it persists, contact the Upside team |

## See also

- [auto-airdrop](auto-airdrop.md) — what happens after registration
- [query-account](query-account.md) — check balance after airdrop lands
- [_shared/signing.md](../_shared/signing.md) — signature format details
