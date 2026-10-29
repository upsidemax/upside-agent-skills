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

## 2. Endpoint reachable

Default is Mainnet (`https://upsidemax.xyz`, real funds); Devnet is `https://dev.upsidemax.xyz`. Tell the user which one you are about to use.

```bash
curl -s -m 5 -X POST https://upsidemax.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"marketState","asset":"1"}'
```

Expected: JSON starting with `{"type":"marketState","asset":"1",…}`.

Failure modes:
- **Timeout / connection refused** → retry shortly; if it persists, contact the UpsideMAX team.
- **HTML response** → the request did not reach the API. Check the URL and that it is a `POST`; retry shortly; if it persists, contact the UpsideMAX team.
- **HTTP 5xx** → backend unavailable; report and wait.

## 3. Contract exists

Once network is up, check that at least contractId=1 exists:

```bash
curl -s -X POST https://upsidemax.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"marketState","asset":"1"}' | grep -q '"asset":"1"' && echo "contract 1 exists"
```

If the response has `markPx: "0"` and `priceReady: false`, **the contract exists but is not ready to match orders yet**. Orders will be accepted (HTTP 202) but silently dropped by the matching engine. Not a blocker for skill demo, but do warn the user before placing orders on such a contract.

## 4. Invitation code

Registration requires an invitation code on Mainnet and Devnet, supplied at envelope level as `inviteCode`. Check that it is set before registering:

```bash
[ -n "$UPSIDE_INVITE_CODE" ] && echo "invite code set" || echo "set UPSIDE_INVITE_CODE first"
```

Without it, `registerAccount` returns `http 400 "inviteCode required"`. Request a code from the UpsideMAX team. Codes are single-use, so do not spend one on a probe registration.
