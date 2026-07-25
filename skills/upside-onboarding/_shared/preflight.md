# Preflight checks

Run these before any skill starts real work. Fail fast if something's off.

## 1. Python deps

```bash
python3 -c "import eth_keys, eth_utils, requests, websocket; print('deps ok')"
```

If any import fails:
```bash
./install.sh
```

## 2. QA reachable

```bash
curl -s -m 5 -X POST https://dev.upsidemax.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"marketState","asset":"1"}'
```

Expected: JSON starting with `{"type":"marketState","asset":"1",…}`.

Failure modes:
- **Timeout / connection refused** → retry shortly; if it persists, contact the Upside team.
- **HTML response** → nginx SPA fallback; the domain's `/info` proxy is misconfigured. Retry shortly; if it persists, contact the Upside team.
- **HTTP 5xx** → backend unavailable; report and wait.

## 3. Contract exists

Once network is up, check that at least contractId=1 exists:

```bash
curl -s -X POST https://dev.upsidemax.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"marketState","asset":"1"}' | grep -q '"asset":"1"' && echo "contract 1 exists"
```

If the response has `markPx: "0"` and `priceReady: false`, **the contract exists but is not ready to match orders yet**. Orders will be accepted (HTTP 202) but silently dropped by the matching engine. Not a blocker for skill demo, but do warn the user before placing orders on such a contract.

## 4. Invite gate

```bash
# Register a fresh wallet without alpha test invitation code
python3 -c "
from examples.common import send_exchange, new_wallet, addr_of
pk, addr = new_wallet()
code, r = send_exchange(pk, {'type':'registerAccount','address':addr})
print('http', code, 'body', r)
"
```

Two possible outcomes:
- `http 200` → invite gate is off; skills won't need `inviteCode`.
- `http 400 "inviteCode required"` → gate is on; an alpha test invitation code must be supplied at envelope level.

If the gate is on, request an alpha test invitation code from the Upside team and set it via the `UPSIDE_INVITE_CODE` environment variable. Including it when the gate is off is a no-op.
