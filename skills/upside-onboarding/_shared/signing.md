# EIP-712 signing protocol

Every write to `POST /exchange` carries a secp256k1 signature over an EIP-712 digest. Get any detail wrong and backend returns 401 `SIGNATURE_INVALID` with "signature recovery failed".

## Envelope shape

```json
{
  "action":    { "type": "…", …arbitrary fields… },
  "signature": { "r": "0x…", "s": "0x…", "v": 27 | 28 },
  "nonce":     1784510817898,
  "inviteCode": "<alpha test invitation code>" // ONLY for registerAccount, and ONLY when backend requires
}
```

Everything except `action` is envelope-level. In particular: **`inviteCode` and `nonce` do NOT go inside `action`.** Putting `inviteCode` inside `action` is the #1 mistake — backend returns `inviteCode required` and won't hint at the fix.

## Domain

```
name              = "Exchange"
version           = "1"
chainId           = 9767
verifyingContract = 0x0000000000000000000000000000000000000000
```

Standard EIP-712: `keccak256(0x1901 || domainSeparator || structHash)`. `domainSeparator` = `keccak256(EIP712Domain-typeHash || keccak256(name) || keccak256(version) || chainId || verifyingContract)`.

## Two paths — auto-routed by `action.type`

### Typed path (account-level actions)

For `registerAccount`, `approveAgent`, `revokeAgent`, `lockCollateral`, `unlockCollateral`, `transferBetweenDeployers` — each has its own typed struct. Fields are extracted from `action` and encoded per EIP-712 rules.

Example — `approveAgent`:
```
type-string: ApproveAgent(address agentAddress,string agentName,uint64 validUntil,uint64 nonce)
struct hash: keccak256(typeHash || agentAddress || keccak256(agentName) || validUntil || nonce)
```

Field encoding: `string → keccak256(utf8)`, `address → 20 bytes left-padded to 32`, `uintN → 32-byte big-endian`.

**Optional fields must still be present on the wire.** Client fills defaults (`agentName: ""`, `validUntil: 0`) into the action dict before signing so the JSON body matches the digest. Missing them causes `signature recovery failed` — server encodes missing string / uint differently than client's fallback.

Typed-action type-strings:

| action | typed struct |
|---|---|
| `registerAccount` | `RegisterAccount(address address,uint64 nonce)` |
| `approveAgent` | `ApproveAgent(address agentAddress,string agentName,uint64 validUntil,uint64 nonce)` |
| `revokeAgent` | `RevokeAgent(address agentAddress,uint64 nonce)` |
| `lockCollateral` | `LockCollateral(uint32 marketDeployerId,uint32 coinId,string amount,uint64 nonce)` |
| `unlockCollateral` | `UnlockCollateral(uint32 marketDeployerId,uint32 coinId,string amount,uint64 nonce)` |
| `transferBetweenDeployers` | `TransferBetweenDeployers(uint32 fromMarketDeployerId,uint32 toMarketDeployerId,uint32 coinId,string amount,uint64 nonce)` |

### Agent path (everything else — trading actions)

For all trading actions (`order`, `cancel`, `cancelByCloid`, `modify`, `cancelAll`, `tpSl`, `cancelTpSl`, `updateLeverage`, `batchCancel`, etc.), the whole canonical JSON of `action` is folded into a single `actionHash` inside an `Agent` wrapper:

```
type-string: Agent(string source,bytes32 actionHash)
canonical  : json.dumps(action, sort_keys=True, separators=(",", ":"))
actionHash = keccak256(canonical || nonce.to_bytes(8, "big"))
struct hash: keccak256(typeHash || keccak256("b") || actionHash)
```

`"b"` is the Agent-path source tag.

Canonical JSON must use `sort_keys=True` and no whitespace (`separators=(",",":")`) — matches server exactly.

## Reference implementation

```python
import json
from eth_account import Account
from eth_utils import keccak

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

_TYPED = {
  "registerAccount": (b"RegisterAccount(address address,uint64 nonce)",
    lambda a, n: [_addr(a.get("address")), _uint(n)]),
  "approveAgent": (b"ApproveAgent(address agentAddress,string agentName,uint64 validUntil,uint64 nonce)",
    lambda a, n: [_addr(a.get("agentAddress")), _str(a.get("agentName")),
                  _uint(a.get("validUntil")), _uint(n)]),
  # …see examples/eip712.py for the full table
}

_TYPED_DEFAULTS = {"approveAgent": {"agentName": "", "validUntil": 0}}


def eip712_digest(action, nonce):
    t = action.get("type")
    if t in _TYPED:
        # Inject default fields so wire JSON matches the digest
        for k, v in _TYPED_DEFAULTS.get(t, {}).items():
            action.setdefault(k, v)
        type_str, fields = _TYPED[t]
        struct_hash = keccak(keccak(type_str) + b"".join(fields(action, nonce)))
    else:
        canonical = json.dumps(action, sort_keys=True, separators=(",", ":")).encode()
        action_hash = keccak(canonical + int(nonce).to_bytes(8, "big"))
        struct_hash = keccak(keccak(_AGENT_TYPE) + keccak(SOURCE.encode()) + action_hash)
    return keccak(b"\x19\x01" + _DOMAIN_SEP + struct_hash)


def sign_envelope(pk, action, nonce=None, invite_code=None):
    import time
    if nonce is None:
        nonce = int(time.time() * 1000)
    digest = eip712_digest(action, nonce)
    sig = Account._sign_hash(digest, pk.to_hex())
    env = {
        "action": action,
        "signature": {
            "r": "0x" + sig.r.to_bytes(32, "big").hex(),
            "s": "0x" + sig.s.to_bytes(32, "big").hex(),
            "v": sig.v if sig.v >= 27 else sig.v + 27,
        },
        "nonce": nonce,
    }
    if invite_code:
        env["inviteCode"] = invite_code
    return env
```

Used everywhere in [`examples/common.py`](../../../examples/common.py). Full typed table in [`examples/eip712.py`](../../../examples/eip712.py).

## Signature verification (what backend does)

Backend:
1. Reads `envelope.action`, `envelope.nonce`.
2. Routes by `action.type` → typed or Agent path.
3. For typed path: extract known fields from `action`, encode per schema, compute struct hash, wrap in EIP-712 digest.
4. For Agent path: serialize `action` with `sort_keys` + no whitespace, hash with `nonce` bytes, wrap in `Agent(source="b", …)` struct.
5. Recover signer from `(r, s, v)` and the digest.
6. Check: does recovered signer match `action.address` (for registerAccount) or an approved-agent/master lookup?

## Common signing errors

| symptom | likely cause |
|---|---|
| `http 401 SIGNATURE_INVALID` "recovered address … does not match action.address" | signed with the wrong key for the target address |
| `http 401 SIGNATURE_INVALID` "signature recovery failed" | digest mismatch. Most common: typed action missing an optional field on the wire (`agentName`, `validUntil`, etc.). Client must inject defaults into `action` before signing. |
| `http 400 "inviteCode required"` on registerAccount | `inviteCode` was placed inside `action` instead of at envelope level |
| `http 400 "nonce already used"` (errorCode 31) | replay: same envelope sent twice, or an old nonce reused |

## Nonces

- Millisecond Unix timestamp.
- Backend enforces uniqueness per signer, and rejects nonces "too far in the future" (currently anything more than ~24h ahead).
- Nonces from the recent past are typically accepted (backend uses a bounded replay-uniqueness window rather than strict monotonicity).
- If you're rapid-firing, add `+i` when building successive nonces to avoid ms-collisions.

## Which key signs what?

| action | signer |
|---|---|
| `registerAccount` | the address's own key (must match `action.address`) |
| `order`, `cancel`, `modify`, `tpSl`, … (TRADE class) | account master's key **or** an approved agent's key |
| `lockCollateral`, `unlockCollateral` (FUND) | master's key only |
| `approveAgent`, `revokeAgent` (account-level GOV) | master's key only |
