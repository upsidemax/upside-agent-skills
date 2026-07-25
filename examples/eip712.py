"""
EIP-712 signing for the Upside `/exchange` endpoint.

Digest is standard EIP-712 (domain name="Exchange" / version="1" / chainId=9767 /
verifyingContract=0x0). Two auto-routed paths, selected by ``action["type"]``:

* **Agent path** (trading / programmatic, most actions): the whole canonical action
  is folded into one ``actionHash`` carried by ``Agent(string source, bytes32 actionHash)``.
* **Typed path** (fund / permission actions): a per-action field-level EIP-712 struct.
  Covers registerAccount / approveAgent / revokeAgent / lockCollateral /
  unlockCollateral / transferBetweenDeployers.

Field encoding: string -> keccak256(utf8); address -> 20 bytes left-padded to 32;
uintN -> 32-byte big-endian.
"""

import json

from eth_utils import keccak

# ── domain (single fixed value; must match server Eip712) ──
CHAIN_ID = 9767
NAME = "Exchange"
VERSION = "1"
SOURCE = "b"  # Agent-path environment tag

_AGENT_TYPE = b"Agent(string source,bytes32 actionHash)"


def _uint(v) -> bytes:
    """Encode uint. Missing (None) defaults to 0 — matches server treatment of
    optional numeric fields like `validUntil` (0 = permanent)."""
    if v is None:
        v = 0
    return int(v).to_bytes(32, "big")


def _addr(s) -> bytes:
    if s is None:
        raise ValueError("EIP-712 address field is missing")
    h = s[2:] if s[:2] in ("0x", "0X") else s
    if len(h) != 40:
        raise ValueError(f"EIP-712 bad address: {s!r}")
    return b"\x00" * 12 + bytes.fromhex(h)


def _str(s) -> bytes:
    """Encode string. Missing (None) defaults to empty — matches server
    treatment of optional string fields like `agentName` (empty = anon slot)."""
    if s is None:
        s = ""
    return keccak(str(s).encode())


# type-string + field-encoder for each typed action (nonce appended by builder)
_TYPED = {
    "registerAccount": (
        b"RegisterAccount(address address,uint64 nonce)",
        lambda a, n: [_addr(a.get("address")), _uint(n)],
    ),
    "approveAgent": (
        b"ApproveAgent(address agentAddress,string agentName,uint64 validUntil,uint64 nonce)",
        lambda a, n: [_addr(a.get("agentAddress")), _str(a.get("agentName")),
                      _uint(a.get("validUntil")), _uint(n)],
    ),
    "revokeAgent": (
        b"RevokeAgent(address agentAddress,uint64 nonce)",
        lambda a, n: [_addr(a.get("agentAddress")), _uint(n)],
    ),
    "lockCollateral": (
        b"LockCollateral(uint32 marketDeployerId,uint32 coinId,string amount,uint64 nonce)",
        lambda a, n: [_uint(a["marketDeployerId"]), _uint(a["coinId"]),
                      _str(a.get("amount")), _uint(n)],
    ),
    "unlockCollateral": (
        b"UnlockCollateral(uint32 marketDeployerId,uint32 coinId,string amount,uint64 nonce)",
        lambda a, n: [_uint(a["marketDeployerId"]), _uint(a["coinId"]),
                      _str(a.get("amount")), _uint(n)],
    ),
    "transferBetweenDeployers": (
        b"TransferBetweenDeployers(uint32 fromMarketDeployerId,uint32 toMarketDeployerId,"
        b"uint32 coinId,string amount,uint64 nonce)",
        lambda a, n: [_uint(a["fromMarketDeployerId"]), _uint(a["toMarketDeployerId"]),
                      _uint(a["coinId"]), _str(a.get("amount")), _uint(n)],
    ),
}


# Defaults for optional fields in typed actions. Server requires these fields
# to be PRESENT in the wire JSON — missing them causes signature recovery
# failure (server's fallback encoding differs from ours). We normalize the
# action dict in-place so the signed payload and the wire JSON match.
_TYPED_DEFAULTS = {
    "approveAgent": {"agentName": "", "validUntil": 0},
}


def _normalize_typed_action(action: dict) -> None:
    """Inject default values for optional typed-action fields, in-place."""
    defaults = _TYPED_DEFAULTS.get(action.get("type"))
    if defaults:
        for key, val in defaults.items():
            action.setdefault(key, val)


def _domain_separator() -> bytes:
    dom_type = (b"EIP712Domain(string name,string version,"
                b"uint256 chainId,address verifyingContract)")
    return keccak(
        keccak(dom_type)
        + keccak(NAME.encode())
        + keccak(VERSION.encode())
        + _uint(CHAIN_ID)
        + b"\x00" * 32  # verifyingContract = 0x0
    )


_DOMAIN_SEPARATOR = _domain_separator()


def eip712_digest(action: dict, nonce: int) -> bytes:
    """Compute the 32-byte EIP-712 digest for ``action`` + ``nonce``.

    Routes by ``action["type"]`` to the Agent or typed path. For typed actions,
    mutates ``action`` in-place to inject default values for optional fields
    (e.g. approveAgent's ``agentName`` / ``validUntil``) so that the wire JSON
    matches what we signed. Raises on a typed action with a missing REQUIRED
    field (e.g. approveAgent without agentAddress).
    """
    action_type = action.get("type")
    typed = _TYPED.get(action_type)
    if typed is not None:
        _normalize_typed_action(action)
        type_str, build_fields = typed
        struct_hash = keccak(keccak(type_str) + b"".join(build_fields(action, nonce)))
    else:
        canonical = json.dumps(action, sort_keys=True, separators=(",", ":")).encode()
        action_hash = keccak(canonical + int(nonce).to_bytes(8, "big"))
        struct_hash = keccak(keccak(_AGENT_TYPE) + keccak(SOURCE.encode()) + action_hash)
    return keccak(b"\x19\x01" + _DOMAIN_SEPARATOR + struct_hash)


def sign_signature(private_key, action: dict, nonce: int) -> dict:
    """Sign ``action`` + ``nonce`` and return the envelope ``signature`` dict."""
    from eth_account import Account

    digest = eip712_digest(action, nonce)
    sig = Account._sign_hash(digest, private_key)
    return {
        "r": "0x" + sig.r.to_bytes(32, "big").hex(),
        "s": "0x" + sig.s.to_bytes(32, "big").hex(),
        "v": sig.v if sig.v >= 27 else sig.v + 27,
    }
