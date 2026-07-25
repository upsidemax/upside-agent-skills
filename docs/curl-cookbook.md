# curl Cookbook

Pure `curl` recipes for every action in the skill — for developers who don't want to run Python.

## Prerequisites

- `curl` (any recent version)
- `jq` (for pretty-printing JSON responses; optional)
- `python3` with `eth-account`, `eth-keys`, `eth-utils` — **only** for signing writes. Reads don't need it.

Install the Python signing deps once:
```bash
pip install eth-account eth-keys eth-utils 'eth-hash[pycryptodome]'
```

`/info` (reads) works with pure curl. `/exchange` (writes) needs an EIP-712 signature — there is no clean pure-shell way to produce a secp256k1 keccak-signed envelope, so we call a small Python helper from inside the shell script.

## Constants for the examples

```bash
export QA_BASE=https://dev.upsidemax.xyz
```

## /info — pure curl

### Market state
```bash
curl -sS -X POST $QA_BASE/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"marketState","asset":"1"}' | jq
```

### Order book
```bash
curl -sS -X POST $QA_BASE/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"l2Book","asset":"1"}' | jq
```

### Account balance (both layers)
```bash
# mo=0 (DexLedger, chain-level unlocked)
curl -sS -X POST $QA_BASE/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"userAccount","accountId":"5","marketDeployerId":0}' | jq

# MO=1 (trading margin)
curl -sS -X POST $QA_BASE/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"userAccount","accountId":"5","marketDeployerId":1}' | jq
```

**Note**: the field is `marketDeployerId`, NOT `marketOwnerId`. Using `marketOwnerId` returns null fields.

### Open orders
```bash
curl -sS -X POST $QA_BASE/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"userOrders","accountId":"5","marketDeployerId":1,"contractId":0}' | jq
```

### List agents (bot keys) under an account
```bash
curl -sS -X POST $QA_BASE/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"userAgents","accountId":"5"}' | jq
```

## /exchange — signed writes

Every write is signed via EIP-712. The signing helper below takes an action JSON + private key, computes the correct digest (auto-routing between typed struct and Agent-wrapped canonical action), signs, and prints the full envelope for curl.

Signing spec details: [../skills/upside-onboarding/_shared/signing.md](../skills/upside-onboarding/_shared/signing.md).

### The signing helper (paste this into your shell once per session)

```bash
sign_envelope() {
  local privkey="$1"
  local action_json="$2"
  local invite_code="${3:-}"
  python3 - "$privkey" "$action_json" "$invite_code" <<'PY'
import json, sys, time
from eth_account import Account
from eth_utils import keccak

# --- EIP-712 domain ---
CHAIN_ID = 9767
NAME = "Exchange"
VERSION = "1"
SOURCE = "b"

def _uint(v):    return int(v or 0).to_bytes(32, "big")
def _str(s):     return keccak((s or "").encode())
def _addr(s):
    h = s[2:] if s[:2].lower() == "0x" else s
    return b"\x00" * 12 + bytes.fromhex(h)

_DOMAIN_SEP = keccak(
    keccak(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
    + keccak(NAME.encode()) + keccak(VERSION.encode())
    + _uint(CHAIN_ID) + b"\x00" * 32
)
_AGENT_TYPE = b"Agent(string source,bytes32 actionHash)"

# typed action encoders (extend as needed)
_TYPED = {
    "registerAccount": (
        b"RegisterAccount(address address,uint64 nonce)",
        lambda a, n: [_addr(a.get("address")), _uint(n)]),
    "approveAgent": (
        b"ApproveAgent(address agentAddress,string agentName,uint64 validUntil,uint64 nonce)",
        lambda a, n: [_addr(a.get("agentAddress")), _str(a.get("agentName")),
                      _uint(a.get("validUntil")), _uint(n)]),
    "revokeAgent": (
        b"RevokeAgent(address agentAddress,uint64 nonce)",
        lambda a, n: [_addr(a.get("agentAddress")), _uint(n)]),
    "lockCollateral": (
        b"LockCollateral(uint32 marketDeployerId,uint32 coinId,string amount,uint64 nonce)",
        lambda a, n: [_uint(a["marketDeployerId"]), _uint(a["coinId"]),
                      _str(a.get("amount")), _uint(n)]),
    "unlockCollateral": (
        b"UnlockCollateral(uint32 marketDeployerId,uint32 coinId,string amount,uint64 nonce)",
        lambda a, n: [_uint(a["marketDeployerId"]), _uint(a["coinId"]),
                      _str(a.get("amount")), _uint(n)]),
}
# Inject defaults for optional typed fields into the action dict so the wire
# JSON matches what we sign. Server won't fall back the same way.
_TYPED_DEFAULTS = {"approveAgent": {"agentName": "", "validUntil": 0}}


def eip712_digest(action, nonce):
    t = action.get("type")
    if t in _TYPED:
        for k, v in _TYPED_DEFAULTS.get(t, {}).items():
            action.setdefault(k, v)
        type_str, fields = _TYPED[t]
        struct_hash = keccak(keccak(type_str) + b"".join(fields(action, nonce)))
    else:
        canonical = json.dumps(action, sort_keys=True, separators=(",", ":")).encode()
        action_hash = keccak(canonical + int(nonce).to_bytes(8, "big"))
        struct_hash = keccak(keccak(_AGENT_TYPE) + keccak(SOURCE.encode()) + action_hash)
    return keccak(b"\x19\x01" + _DOMAIN_SEP + struct_hash)


privkey_hex = sys.argv[1].removeprefix("0x")
action = json.loads(sys.argv[2])
invite = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None

nonce = int(time.time() * 1000)
digest = eip712_digest(action, nonce)
sig = Account._sign_hash(digest, "0x" + privkey_hex)

env = {
    "action": action,
    "signature": {
        "r": "0x" + sig.r.to_bytes(32, "big").hex(),
        "s": "0x" + sig.s.to_bytes(32, "big").hex(),
        "v": sig.v if sig.v >= 27 else sig.v + 27,
    },
    "nonce": nonce,
}
if invite:
    env["inviteCode"] = invite
print(json.dumps(env))
PY
}
```

### Register a new account

Step 1 — generate a fresh private key:
```bash
PRIVKEY=$(python3 -c "import secrets; print('0x' + secrets.token_hex(32))")
ADDR=$(python3 -c "from eth_keys import keys; print(keys.PrivateKey(bytes.fromhex('$PRIVKEY'[2:])).public_key.to_address())")
echo "private key: $PRIVKEY"
echo "address:     $ADDR"
```

**Save `$PRIVKEY` somewhere safe** — you'll need it for every subsequent write.

Step 2 — register (with envelope-level alpha test invitation code). Request an alpha test invitation code from the Upside team and set it via the `UPSIDE_INVITE_CODE` environment variable:
```bash
ENV=$(sign_envelope "$PRIVKEY" "{\"type\":\"registerAccount\",\"address\":\"$ADDR\"}" "$UPSIDE_INVITE_CODE")
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

Response — success:
```json
{"status":"ok","response":{"type":"registerAccount","accountId":"5"}}
```

Response — already registered:
```json
{"status":"error","code":"ACCOUNT_ALREADY_EXISTS","message":"address already registered: accountId=5"}
```

Both count as success — save the `accountId` (aid).

Save it:
```bash
export AID=5   # from the response
```

### Wait for the auto-airdrop

Simplest — a bash loop:
```bash
for i in $(seq 1 15); do
  BAL=$(curl -sS -X POST $QA_BASE/info \
    -H 'Content-Type: application/json' \
    -d "{\"type\":\"userAccount\",\"accountId\":\"$AID\",\"marketDeployerId\":1}" \
    | jq -r '.crossEquity // "0"')
  echo "t=$((i*3))s  MO=1 crossEquity=$BAL"
  if [ "$BAL" != "0" ] && [ "$BAL" != "null" ]; then
    echo "✓ funds arrived"
    break
  fi
  sleep 3
done
```

If nothing arrives after 45 s → register a fresh wallet (misses are per-registration).

### Place a limit order

```bash
ACTION='{"type":"order","grouping":"na","orders":[{"a":1,"b":true,"p":"100","s":"1","r":false,"t":{"limit":{"tif":"Gtc"}}}]}'
ENV=$(sign_envelope "$PRIVKEY" "$ACTION")
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

Response: `http 202`, `{"status":"accepted","response":{"type":"order","data":{"count":1}}}`.

`count: 1` just means the order was accepted at HTTP layer. Confirm it actually landed in the book with an `/info userOrders` call after 1-2 s.

### Cancel one order

```bash
OID=12345
ACTION="{\"type\":\"cancel\",\"cancels\":[{\"a\":1,\"o\":$OID}]}"
ENV=$(sign_envelope "$PRIVKEY" "$ACTION")
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

### Cancel all on a contract

```bash
ENV=$(sign_envelope "$PRIVKEY" '{"type":"cancelAll","a":1}')
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

Response: `{"limitCancelled": N, "conditionalCancelled": M}`.

### Modify an order

```bash
OID=12345
ACTION="{\"type\":\"modify\",\"oid\":$OID,\"order\":{\"a\":1,\"b\":true,\"p\":\"101\",\"s\":\"2\",\"r\":false,\"t\":{\"limit\":{\"tif\":\"Gtc\"}}}}"
ENV=$(sign_envelope "$PRIVKEY" "$ACTION")
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

### Update leverage

```bash
ENV=$(sign_envelope "$PRIVKEY" '{"type":"updateLeverage","a":1,"leverage":5,"isIsolated":false}')
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

### Approve an agent (bot key)

```bash
AGENT_ADDR=0xbotAddressHere
ACTION="{\"type\":\"approveAgent\",\"agentAddress\":\"$AGENT_ADDR\",\"agentName\":\"my-bot\"}"
ENV=$(sign_envelope "$PRIVKEY" "$ACTION")
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

### Revoke an agent

```bash
ENV=$(sign_envelope "$PRIVKEY" "{\"type\":\"revokeAgent\",\"agentAddress\":\"$AGENT_ADDR\"}")
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

### TP/SL for a position

```bash
ACTION='{"type":"tpSl","a":1,"positionSide":0,"isPositionTpsl":true,"tpPrice":"1500","slPrice":"400","tpTriggerType":0,"slTriggerType":0}'
ENV=$(sign_envelope "$PRIVKEY" "$ACTION")
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

Cancel:
```bash
ENV=$(sign_envelope "$PRIVKEY" '{"type":"cancelTpSl","a":1,"positionSide":0}')
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' \
  -d "$ENV" | jq
```

### Move DexLedger → MO=1 margin

If your airdrop landed in mo=0 instead of MO=1, migrate:

```bash
ENV=$(sign_envelope "$PRIVKEY" '{"type":"enrollUserToMarketOwner","marketDeployerId":1}')
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' -d "$ENV" | jq

ENV=$(sign_envelope "$PRIVKEY" '{"type":"lockCollateral","marketDeployerId":1,"coinId":1,"amount":"1000000000000"}')
curl -sS -X POST $QA_BASE/exchange \
  -H 'Content-Type: application/json' -d "$ENV" | jq
```

## Complete quick-start script

Copy-paste this whole block into a shell to run the end-to-end flow:

```bash
#!/usr/bin/env bash
set -e
export QA_BASE=${QA_BASE:-https://dev.upsidemax.xyz}

# EIP-712 signing helper — see "The signing helper" section above for full comments.
sign_envelope() {
  python3 - "$1" "$2" "${3:-}" <<'PY'
import json, sys, time
from eth_account import Account
from eth_utils import keccak

CHAIN_ID, NAME, VERSION, SOURCE = 9767, "Exchange", "1", "b"

def _uint(v): return int(v or 0).to_bytes(32, "big")
def _str(s):  return keccak((s or "").encode())
def _addr(s):
    h = s[2:] if s[:2].lower() == "0x" else s
    return b"\x00" * 12 + bytes.fromhex(h)

_DOM = keccak(
    keccak(b"EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
    + keccak(NAME.encode()) + keccak(VERSION.encode()) + _uint(CHAIN_ID) + b"\x00" * 32)
_AGENT = b"Agent(string source,bytes32 actionHash)"
_TYPED = {
    "registerAccount": (b"RegisterAccount(address address,uint64 nonce)",
        lambda a, n: [_addr(a.get("address")), _uint(n)]),
    "approveAgent": (b"ApproveAgent(address agentAddress,string agentName,uint64 validUntil,uint64 nonce)",
        lambda a, n: [_addr(a.get("agentAddress")), _str(a.get("agentName")),
                      _uint(a.get("validUntil")), _uint(n)]),
}
_DEF = {"approveAgent": {"agentName": "", "validUntil": 0}}

def digest(action, nonce):
    t = action.get("type")
    if t in _TYPED:
        for k, v in _DEF.get(t, {}).items(): action.setdefault(k, v)
        ts, fields = _TYPED[t]
        sh = keccak(keccak(ts) + b"".join(fields(action, nonce)))
    else:
        c = json.dumps(action, sort_keys=True, separators=(",", ":")).encode()
        sh = keccak(keccak(_AGENT) + keccak(SOURCE.encode())
                    + keccak(c + int(nonce).to_bytes(8, "big")))
    return keccak(b"\x19\x01" + _DOM + sh)

action = json.loads(sys.argv[2])
invite = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
nonce = int(time.time() * 1000)
sig = Account._sign_hash(digest(action, nonce), "0x" + sys.argv[1].removeprefix("0x"))
env = {"action": action,
       "signature": {"r": "0x" + sig.r.to_bytes(32,"big").hex(),
                     "s": "0x" + sig.s.to_bytes(32,"big").hex(),
                     "v": sig.v if sig.v >= 27 else sig.v + 27},
       "nonce": nonce}
if invite: env["inviteCode"] = invite
print(json.dumps(env))
PY
}

echo "=== 1. Generate wallet ==="
PRIVKEY=$(python3 -c "import secrets; print('0x' + secrets.token_hex(32))")
ADDR=$(python3 -c "from eth_keys import keys; print(keys.PrivateKey(bytes.fromhex('$PRIVKEY'[2:])).public_key.to_address())")
echo "  private key: $PRIVKEY"
echo "  address:     $ADDR"

echo "=== 2. Register ==="
# Set UPSIDE_INVITE_CODE to an alpha test invitation code obtained from the Upside team.
ENV=$(sign_envelope "$PRIVKEY" "{\"type\":\"registerAccount\",\"address\":\"$ADDR\"}" "$UPSIDE_INVITE_CODE")
RESP=$(curl -sS -X POST $QA_BASE/exchange -H 'Content-Type: application/json' -d "$ENV")
echo "  $RESP"
AID=$(echo "$RESP" | python3 -c "import json,sys,re; d=json.load(sys.stdin); aid=d.get('response',{}).get('accountId'); m=re.search(r'accountId=(\d+)', d.get('message','') or ''); print(aid or (m.group(1) if m else ''))")
echo "  accountId: $AID"

echo "=== 3. Wait for airdrop ==="
for i in $(seq 1 15); do
  BAL=$(curl -sS -X POST $QA_BASE/info -H 'Content-Type: application/json' \
    -d "{\"type\":\"userAccount\",\"accountId\":\"$AID\",\"marketDeployerId\":1}" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('crossEquity','0'))")
  echo "  t=$((i*3))s  MO=1 crossEquity=$BAL"
  [ "$BAL" != "0" ] && [ "$BAL" != "null" ] && break
  sleep 3
done

echo "=== 4. Place order (buy 1 @ 100) ==="
ENV=$(sign_envelope "$PRIVKEY" '{"type":"order","grouping":"na","orders":[{"a":1,"b":true,"p":"100","s":"1","r":false,"t":{"limit":{"tif":"Gtc"}}}]}')
curl -sS -X POST $QA_BASE/exchange -H 'Content-Type: application/json' -d "$ENV"

sleep 2

echo
echo "=== 5. List orders ==="
curl -sS -X POST $QA_BASE/info -H 'Content-Type: application/json' \
  -d "{\"type\":\"userOrders\",\"accountId\":\"$AID\",\"marketDeployerId\":1,\"contractId\":0}"

echo
echo "=== 6. Cancel all on contract 1 ==="
ENV=$(sign_envelope "$PRIVKEY" '{"type":"cancelAll","a":1}')
curl -sS -X POST $QA_BASE/exchange -H 'Content-Type: application/json' -d "$ENV"
echo
```

Save to `quick_start.sh`, `chmod +x`, run.

## WebSocket via `websocat` (bonus)

If you have `websocat` installed:

```bash
websocat wss://dev.upsidemax.xyz/ws
# then paste each subscribe line:
{"method":"subscribe","subscription":{"type":"l2Book","asset":"1"}}
```

Or for one-shot use `curl`'s HTTP/2 mode — but this is where `websocat` really is worth installing.

## What next

- Full flow with error handling: [getting-started.md](getting-started.md)
- Error decoder: [faq.md](faq.md)
- Full action reference: [../skills/upside-trading/references/place-order.md](../skills/upside-trading/references/place-order.md)
- WS protocol details: [../skills/upside-websocket/references/websocket-protocol.md](../skills/upside-websocket/references/websocket-protocol.md)
