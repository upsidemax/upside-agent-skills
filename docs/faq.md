# FAQ / Troubleshooting

This page lists common errors and their resolutions. If your issue is not listed here, consult the per-topic references linked at the bottom.

## Install / setup

### `ModuleNotFoundError: No module named 'eth_keys'`
Run `./install.sh` or `pip install eth-keys eth-utils requests websocket-client eth-hash[pycryptodome]`.

### `pip install --user ... permission denied`
You're in a restricted environment (Docker/CI). Use a venv:
```bash
python3 -m venv .venv
source .venv/bin/activate
./install.sh
```

### `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+`
On macOS with LibreSSL. Just a warning — ignore. If it bothers you: `pip install urllib3==1.26.18` to pin an older version.

### `install.sh: /bin/bash: bad interpreter`
On Windows, use Git Bash or WSL. Or run the pip commands manually.

## Connectivity

### Timeout hitting `https://dev.upsidemax.xyz/info`
The QA environment may be temporarily unavailable, or your network may be blocking the request.
1. Run `curl -v https://dev.upsidemax.xyz/info` to see what fails.
2. Retry shortly; if it persists, contact the Upside team.

### `POST /info` returns HTML (not JSON)
The endpoint is not currently proxying `/info`. Retry shortly; if it persists, contact the Upside team.

### WebSocket connects but no messages
You are using an unsupported subscription format. The server uses a JSON subscribe protocol with `{"method":"subscribe","subscription":{...}}` frames. Change:
```json
✗ {"msg":"Subscribe", "channels":["l2Book.1"]}
✓ {"method":"subscribe", "subscription":{"type":"l2Book", "asset":"1"}}
```
See [../skills/upside-websocket/references/websocket-protocol.md](../skills/upside-websocket/references/websocket-protocol.md).

## Registration

### `http 400 "inviteCode required"`
You put `inviteCode` inside `action`. It belongs at **envelope level**:
```json
✗ {"action":{"type":"registerAccount","address":"0x…","inviteCode":"<invite-code>"}, …}
✓ {"action":{"type":"registerAccount","address":"0x…"}, "inviteCode":"<invite-code>", …}
```
Request an alpha test invitation code from the Upside team and set it via the `UPSIDE_INVITE_CODE` environment variable.

### `http 409 ACCOUNT_ALREADY_EXISTS`
Not an error — you've already registered. Parse the `accountId` from the message:
```python
aid = msg.split("accountId=")[-1].strip()
```
And proceed.

### `http 401 "recovered address … does not match action.address"`
The signature was made by a different private key than the `action.address`. The service requires signer == address for `registerAccount`. Use the key that owns the target address.

## Funds

### `depositNonce = 0` and no funds after 60 seconds
The QA airdrop occasionally does not arrive. The simplest resolution is to register a fresh wallet:
```bash
python3 examples/01_register.py
```
Airdrop misses are typically specific to an individual registration, so a new registration usually succeeds.

### Balance shows `null` for every field
You are querying with `marketOwnerId` instead of `marketDeployerId`. The correct field is `marketDeployerId`; using `marketOwnerId` returns null fields rather than an error.
```json
✗ {"type":"userAccount","accountId":"5","marketOwnerId":1}
✓ {"type":"userAccount","accountId":"5","marketDeployerId":1}
```

### Money is in `chainBalances` (mo=0) but not in `crossCollaterals` (MO=1)
Airdrop landed in DexLedger layer. To trade, migrate to MO=1:
```python
send_exchange(pk, {"type":"enrollUserToMarketOwner","marketDeployerId":1})
send_exchange(pk, {"type":"lockCollateral","marketDeployerId":1,"coinId":1,"amount":"1000000000000"})
```

## Trading

### Order returns `http 202` but doesn't show up in `userOrders`
Matching engine silently dropped it. Common causes:

| cause | check |
|---|---|
| `priceReady: false` on contract | `python3 examples/04_market_info.py <contractId>` |
| Price outside price-band (too far from mark) | Compare `p` to `markPx * (1 ± priceBandBps/10000)` |
| Insufficient `marginAvailableForOrder` | `python3 examples/03_check_balance.py <aid>` |
| Reduce-only (`r: true`) with no matching position | Check `userAccount.positions` |
| Contract paused or delisted | Try a different contract |

### `errorCode: 30 "agent may sign trade actions only"`
Signer is an agent, tried to sign a FUND (deposit/withdraw) or GOV (register/approve) action. Sign with the master key instead.

If you're seeing this on a TRADE action like `order`, your agent binding may have been revoked or expired. Check with `userAgents`.

### `errorCode: 27 "agent address bound to another master"`
That agent address is already approved under a different master. Either use a fresh address, or revoke it from the current master first.

### `errorCode: 28 "named agent quota (3) exceeded"`
You already have 3 named agents. Revoke one, or reuse an existing name (which overwrites the slot).

### `errorCode: 4 "unknown contract"`
The `a` field references a contractId that doesn't exist. Query `marketState` to verify:
```python
info({"type":"marketState","asset":"1"})  # asset is a STRING
```

### `errorCode: 31 "nonce already used"`
Replay — same envelope sent twice. Regenerate with a fresh nonce.

### `errorCode: 31 "nonce too far in the future"`
Nonce > 24h ahead of now. Use `int(time.time() * 1000)`.

### `errorCode: 1 "invalid validUntil (must be 0 or > blo…"`
Passed a past timestamp for `validUntil`. Use `0` for permanent, or a future timestamp.

## WebSocket

### `{"channel":"error","data":{"code":"BAD_SUBSCRIPTION","message":"missing/invalid params for type=l2Book"}}`
Wrong param name. Use `asset` (a string containing contractId):
```json
✗ {"type":"l2Book","coin":"1"}
✗ {"type":"l2Book","contractId":1}
✓ {"type":"l2Book","asset":"1"}
```

### WS connection drops after ~60 s of idle
Server doesn't send heartbeats. Add a client-side ping every 30 s:
```python
import threading, time
def ping_forever(ws):
    while ws.connected:
        try: ws.ping()
        except Exception: break
        time.sleep(30)
threading.Thread(target=ping_forever, args=(ws,), daemon=True).start()
```

### WS returns "unknown subscription type: allMids"
This subscription type is not currently supported. Subscribe to `l2Book` per contract instead.

## Signing

### `http 401 SIGNATURE_INVALID` and I'm sure the key is right
Common causes:
1. Wrong `v` byte (must be 27 or 28, not 0/1)
2. Typed action missing an optional field on the wire (`agentName`, `validUntil`, `amount`, …). The server does not apply the same field defaults the client does, so the field must be present in the JSON. `examples/common.py`'s `sign_envelope` auto-injects defaults; if you implement your own signer, replicate the `_TYPED_DEFAULTS` step.
3. Agent-path canonical JSON has whitespace or wrong key order (must be `sort_keys=True, separators=(",",":")`)
4. Nonce mismatch (envelope-level nonce != nonce passed into the digest)
5. Wrong EIP-712 domain (name/version/chainId must match server: `{Exchange, 1, 9767}`)

Verify with `examples/common.py`'s `sign_envelope` — the reference implementation is correct.

### Envelope-level vs action-level fields
- `action`: contains `type` and action-specific fields
- Envelope-level (SIBLINGS to `action`): `signature`, `nonce`, `inviteCode` (for registerAccount only)

Do NOT put `nonce` or `inviteCode` inside `action`. Do NOT put `type` at envelope level.

## Environment / config

### How do I use a different environment (UAT / mainnet)?
Set `UPSIDE_BASE_URL` in `.env` (or as an env var). `examples/common.py` reads it automatically. Do NOT point at a mainnet URL — all keys generated by these scripts are disposable and QA-only.

### How do I persist my private key across script runs?
Copy `.env.example` to `.env` and fill in `USER_PRIVATE_KEY`. `common.py` reads it automatically if you use the `load_user_wallet()` helper. See [.env.example](../.env.example).

### Can I use TypeScript / Rust / Go instead of Python?
Yes. Port `examples/common.py` (signing + HTTP wrapper). The wire format is language-agnostic — see [../skills/upside-onboarding/_shared/signing.md](../skills/upside-onboarding/_shared/signing.md) for the exact algorithm.

## Getting help

- Full error code table: [../skills/upside-advanced/references/error-codes.md](../skills/upside-advanced/references/error-codes.md)
- API concept guide: [getting-started.md](getting-started.md)
- Skill index: [../skills/README.md](../skills/README.md)
- If your AI coding assistant appears confused, the skill files (`skills/*/SKILL.md`) are intended to be read top to bottom by AI assistants; direct it to read those.
