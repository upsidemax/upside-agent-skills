"""
Shared helpers for all examples.

Imports at the top of every example script:

    from common import (
        BASE_URL, WS_URL, INVITE_CODE,
        sign_envelope, send_exchange, info, new_wallet,
        wait_until, addr_of,
        load_user_wallet,   # optional .env-driven wallet loader
    )

Design notes:
- Signing uses EIP-712 with the domain {name:"Exchange", version:"1", chainId}.
  The chainId follows the environment (Mainnet 9788, Devnet 9767) and is picked
  from BASE_URL; UPSIDE_CHAIN_ID overrides it. Two auto-routed paths (per action type): a typed struct for account-level
  actions (registerAccount / approveAgent / revokeAgent / lockCollateral / …)
  and an Agent-wrapped canonical-action hash for trading actions (order /
  cancel / modify / …). Details in examples/eip712.py + skills/upside-onboarding/
  _shared/signing.md.
- `inviteCode` goes at envelope level, NOT inside `action`.
- REST balance queries use the `marketDeployerId` field.

Optional `.env` support (no external `python-dotenv` dep):
  Copy `.env.example` to `.env` (in repo root) and set USER_PRIVATE_KEY, USER_ACCOUNT_ID.
  Other overrides: UPSIDE_BASE_URL, UPSIDE_WS_URL, UPSIDE_CHAIN_ID.
"""

import os
import time
import secrets
from pathlib import Path

import requests
from eth_account import Account
from eth_keys import keys

from eip712 import chain_id_for, eip712_digest


# ── .env loader (tiny, no external deps) ────────────────────

def _load_dotenv():
    """Read KEY=VALUE lines from .env in repo root; return as dict.

    Only used to bootstrap env vars for THIS process. Does not override existing os.environ.
    Silent on missing file.
    """
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.exists():
        return {}
    data = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        data[k.strip()] = v.strip().strip("'\"")
    return data


_DOTENV = _load_dotenv()


def _env(key, default=None):
    """Get env var, prefer os.environ then .env file then default."""
    return os.environ.get(key) or _DOTENV.get(key) or default


# ── Environment ─────────────────────────────────────────────

# Mainnet by default. For Devnet set UPSIDE_BASE_URL=https://dev.upsidemax.xyz
# (the WebSocket URL and chain id follow it unless set explicitly).
MAINNET_BASE_URL = "https://upsidemax.xyz"
DEVNET_BASE_URL = "https://dev.upsidemax.xyz"

BASE_URL = _env("UPSIDE_BASE_URL", MAINNET_BASE_URL).rstrip("/")
WS_URL = _env("UPSIDE_WS_URL", "wss://" + BASE_URL.split("://", 1)[-1] + "/ws")
CHAIN_ID = int(_env("UPSIDE_CHAIN_ID") or chain_id_for(BASE_URL))

# Invitation code for registerAccount (required on Mainnet and Devnet). Request one from the
# UpsideMAX team and provide it via UPSIDE_INVITE_CODE (or a .env entry). None is bundled.
INVITE_CODE = _env("UPSIDE_INVITE_CODE", "")

HEADERS = {"Connection": "close", "Content-Type": "application/json"}


# ── Wallets ──────────────────────────────────────────────────

def new_wallet():
    """Generate a fresh random private key. Returns (PrivateKey, address)."""
    pk = keys.PrivateKey(bytes.fromhex(secrets.token_hex(32)))
    return pk, pk.public_key.to_address()


def addr_of(pk):
    """Return the lowercase 0x-prefixed address for a private key."""
    return pk.public_key.to_address()


# ── Signing ──────────────────────────────────────────────────

def sign_envelope(pk, action, nonce=None, invite_code=None, chain_id=None):
    """Build a signed request envelope for POST /exchange.

    Signs via EIP-712 (see eip712.py). For typed actions (registerAccount,
    approveAgent, …) this MUTATES `action` in-place to fill default values
    for optional fields — the server needs those defaults present in the wire
    JSON to reproduce the same digest.

    Args:
        pk: eth_keys.PrivateKey instance
        action: dict with a `type` field
        nonce: int millisecond timestamp; auto-filled if None
        invite_code: str; only needed for registerAccount
        chain_id: int; defaults to CHAIN_ID (the configured environment)

    Returns:
        dict ready to be POSTed as JSON.
    """
    if nonce is None:
        nonce = int(time.time() * 1000)
    digest = eip712_digest(action, nonce, chain_id or CHAIN_ID)   # may mutate `action` in-place
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
    if invite_code is not None:
        env["inviteCode"] = invite_code
    return env


# ── HTTP ─────────────────────────────────────────────────────

def _post(path, json_body, base=None, timeout=15, retries=3):
    """POST with a small retry on transient network errors (connection resets, SSL
    blips, timeouts). Re-raises the last error
    only if every attempt fails."""
    url = (base or BASE_URL) + path
    last = None
    for attempt in range(retries):
        try:
            return requests.post(url, json=json_body, headers=HEADERS, timeout=timeout)
        except requests.exceptions.RequestException as e:
            last = e
            if attempt < retries - 1:
                time.sleep(1 + attempt)   # 1s, then 2s backoff
    raise last


def send_exchange(pk, action, base=None, invite_code=None, timeout=15):
    """Sign + POST to /exchange. Returns (http_status, json_body).

    Signs over the chain id of ``base`` when given, otherwise the configured CHAIN_ID."""
    chain_id = chain_id_for(base) if base and base.rstrip("/") != BASE_URL else None
    env = sign_envelope(pk, action, invite_code=invite_code, chain_id=chain_id)
    r = _post("/exchange", env, base=base, timeout=timeout)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"_raw": r.text}


def info(query, base=None, timeout=10):
    """POST /info. Returns json body directly."""
    r = _post("/info", query, base=base, timeout=timeout)
    try:
        return r.json()
    except ValueError:
        return {"_raw": r.text, "_status": r.status_code}


# ── Utilities ────────────────────────────────────────────────

def wait_until(predicate, timeout_sec=60, poll_sec=2, label="condition"):
    """Poll `predicate()` until it returns truthy or timeout. Returns final predicate value or None."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        val = predicate()
        if val:
            return val
        time.sleep(poll_sec)
    print(f"  ! timeout waiting for {label} after {timeout_sec}s")
    return None


def register_account(pk, base=None, invite_code=None):
    """One-liner registerAccount. Returns accountId (string) or None on failure.

    Handles the two success cases:
      - 200 + response.accountId  (fresh)
      - 409 ACCOUNT_ALREADY_EXISTS with 'accountId=N' in message (already registered)
    """
    invite_code = invite_code if invite_code is not None else INVITE_CODE
    if not invite_code:
        print("  ! No invitation code set. Request one from the UpsideMAX team and set UPSIDE_INVITE_CODE.")
        return None
    code, r = send_exchange(pk, {
        "type": "registerAccount",
        "address": addr_of(pk),
    }, base=base, invite_code=invite_code)
    aid = r.get("response", {}).get("accountId")
    if aid:
        return str(aid)
    msg = str(r.get("message", ""))
    if "accountId=" in msg:
        return msg.split("accountId=")[-1].strip()
    print(f"  ! registerAccount failed http={code}: {r}")
    return None


# ── Chain metadata (settle coin, contract list, etc.) ────────

_CONFIGS_CACHE = {}  # keyed by base URL

def configs(base=None, force_refresh=False):
    """Fetch the chain configs snapshot (coins / contracts / marketDeployers).

    Cached per base URL. Pass force_refresh=True to bust.

    Returns the full response dict, or empty dict on failure.
    """
    base = base or BASE_URL
    if not force_refresh and base in _CONFIGS_CACHE:
        return _CONFIGS_CACHE[base]
    resp = info({"type": "configs"}, base=base)
    if resp.get("type") == "configs":
        _CONFIGS_CACHE[base] = resp
    return resp


def get_settle_coin(market_deployer_id=1, base=None):
    """Return the settle coin metadata for a given market deployer.

    Result: {"coinId": int, "name": str, "szDecimals": int, "isMargin": bool, "status": str}
    or None if the MD or its settle coin isn't found.
    """
    cfg = configs(base=base)
    for md in cfg.get("marketDeployers") or []:
        if md.get("marketDeployerId") == market_deployer_id:
            sc_id = md.get("settleCoinId")
            for c in cfg.get("coins") or []:
                if c.get("coinId") == sc_id:
                    return c
    return None


def get_coin(coin_id, base=None):
    """Return coin metadata by coinId, or None."""
    cfg = configs(base=base)
    for c in cfg.get("coins") or []:
        if c.get("coinId") == coin_id:
            return c
    return None


def get_contract(contract_id, base=None):
    """Return contract metadata by contractId, or None."""
    cfg = configs(base=base)
    for c in cfg.get("contracts") or []:
        if c.get("contractId") == contract_id:
            return c
    return None


# ── Balance helpers (auto-detect settle coin) ────────────────

def get_balance(account_id, base=None, market_deployer_id=1):
    """Return (mo0_raw, mo1_raw) — sums the market deployer's SETTLE coin only.

    Auto-detects settle coin via /info configs (cached). If configs is
    unreachable, falls back to coinId=1 to remain usable.
    """
    settle = get_settle_coin(market_deployer_id, base=base)
    sc_id = settle["coinId"] if settle else 1
    r0 = info({"type": "userAccount", "accountId": str(account_id), "marketDeployerId": 0}, base=base)
    r1 = info({"type": "userAccount", "accountId": str(account_id), "marketDeployerId": market_deployer_id}, base=base)
    mo0 = sum(int(c.get("amount", "0")) for c in (r0.get("chainBalances") or []) if c.get("coinId") == sc_id)
    mo1 = sum(int(c.get("amount", "0")) for c in (r1.get("crossCollaterals") or []) if c.get("coinId") == sc_id)
    return mo0, mo1


def get_all_balances(account_id, base=None, market_deployer_id=1):
    """Return {'mo=0': [{coinId, name, szDecimals, raw, layer}, …],
              'MO=<n>': […]}  — every coin the user holds in each layer.

    From the mo=0 response we take chainBalances (DexLedger). From the MO=N
    response we take crossCollaterals + isolatedCollaterals only — backend
    duplicates chainBalances into the MO=N response as a convenience, so we
    dedupe here to avoid double-counting.
    """
    cfg = configs(base=base)
    coins_by_id = {c["coinId"]: c for c in cfg.get("coins") or []}
    result = {}
    for label, mdid, source_fields in [
        ("mo=0", 0, ("chainBalances",)),
        (f"MO={market_deployer_id}", market_deployer_id, ("crossCollaterals", "isolatedCollaterals")),
    ]:
        r = info({"type": "userAccount", "accountId": str(account_id), "marketDeployerId": mdid}, base=base)
        rows = []
        for src_field in source_fields:
            for entry in r.get(src_field) or []:
                cid = entry.get("coinId")
                coin = coins_by_id.get(cid, {"coinId": cid, "name": "?", "szDecimals": 6})
                rows.append({**coin, "raw": int(entry.get("amount", "0")), "layer": src_field})
        result[label] = rows
    return result


def format_amount(raw, coin_or_id_or_name=None, base=None):
    """Render a raw amount with the right coin name + decimals.

    coin_or_id_or_name: a coin dict (from get_coin), or coinId int, or None to
    fall back to the market's settle coin.
    """
    if isinstance(coin_or_id_or_name, dict):
        coin = coin_or_id_or_name
    elif isinstance(coin_or_id_or_name, int):
        coin = get_coin(coin_or_id_or_name, base=base)
    else:
        coin = get_settle_coin(1, base=base)
    if not coin:
        return f"{raw} raw"
    return f"{int(raw) / 10**coin['szDecimals']:,.2f} {coin['name']}"


# Back-compat alias — old code used usdt(). Renders whichever coin is the
# market deployer's settle coin.
def usdt(raw):
    """Deprecated: use format_amount(). Kept for back-compat."""
    return format_amount(raw)


# ── .env-driven wallet loader / saver ───────────────────────

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _save_env(values):
    """Replace/append KEY=VALUE lines in the repo-root `.env` (mode 600)."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    kept = [ln for ln in lines if ln.partition("=")[0].strip() not in values]
    kept += [f"{k}={v}" for k, v in values.items()]
    ENV_PATH.write_text("\n".join(kept) + "\n", encoding="utf-8")
    ENV_PATH.chmod(0o600)
    _DOTENV.update(values)
    return ENV_PATH


def save_wallet(pk, account_id=None):
    """Write USER_PRIVATE_KEY (and USER_ACCOUNT_ID) into the repo-root `.env`.

    `.env` is gitignored and readable only by you (mode 600). The key is never
    printed: on Mainnet it controls real funds, so it must not end up in a
    terminal log or a chat transcript. Existing lines for these keys are replaced.
    """
    values = {"USER_PRIVATE_KEY": "0x" + pk.to_hex()[2:]}
    if account_id is not None:
        values["USER_ACCOUNT_ID"] = str(account_id)
    return _save_env(values)


def _is_mainnet(base=None):
    return (base or BASE_URL).split("://", 1)[-1].split("/", 1)[0] == "upsidemax.xyz"


def funding_hint(base=None):
    """What to tell the user when the account has no balance, per environment."""
    if _is_mainnet(base):
        return ("The account has a zero balance. Deposit funds into the account before\n"
                "  trading, then re-run.")
    return ("The account has a zero balance. For Devnet funds, contact the UpsideMAX team,\n"
            "  then re-run.")


FUNDING_HINT = funding_hint()


def load_user_wallet():
    """Load the user's private key and accountId from `.env` (repo root).

    Returns (PrivateKey, address, accountId_str). Any of the three may be None
    if not set in .env — caller must handle.

    Usage in a script:
        pk, addr, aid = load_user_wallet()
        if not pk:
            print("Set USER_PRIVATE_KEY in .env first (copy from .env.example).")
            return
        # …use pk to sign actions, use aid for /info queries

    Note: USER_ACCOUNT_ID is optional — if unset you can derive it by attempting
    registerAccount (409 returns aid in the message) via register_account(pk).
    """
    pk_hex = _env("USER_PRIVATE_KEY")
    aid = _env("USER_ACCOUNT_ID")
    if not pk_hex:
        return None, None, None
    if pk_hex.startswith("0x"):
        pk_hex = pk_hex[2:]
    pk = keys.PrivateKey(bytes.fromhex(pk_hex))
    return pk, pk.public_key.to_address(), aid


def require_user_wallet():
    """Return (PrivateKey, address, accountId) from `.env`, or exit with a hint.

    Scripts never take a private key on the command line: it would land in the
    shell history and in any AI chat that runs the command.
    """
    pk, addr, aid = load_user_wallet()
    if not pk:
        raise SystemExit("✗ USER_PRIVATE_KEY is not set in .env — run "
                         "`python3 examples/01_register.py` first (it saves the key there).")
    return pk, addr, aid


def load_agent_wallet(create=False):
    """Return (PrivateKey, address) for AGENT_PRIVATE_KEY in `.env`.

    With ``create=True`` a missing agent key is generated and saved (never
    printed). Returns (None, None) when absent and not created.
    """
    pk_hex = _env("AGENT_PRIVATE_KEY")
    if not pk_hex:
        if not create:
            return None, None
        pk, addr = new_wallet()
        _save_env({"AGENT_PRIVATE_KEY": "0x" + pk.to_hex()[2:]})
        return pk, addr
    pk = keys.PrivateKey(bytes.fromhex(pk_hex[2:] if pk_hex.startswith("0x") else pk_hex))
    return pk, pk.public_key.to_address()
