#!/usr/bin/env python3
"""
08_agent_delegation.py — approve an "agent" (API key) that can sign TRADE actions
                          on behalf of the master account.

Concept:
  A `master` account has full authority (TRADE + FUND + GOV).
  A `master` can approve one or more `agent` addresses that get **TRADE-only**
  authority. Agents cannot deposit/withdraw and cannot approve other agents.

  Approve an agent → the agent's private key can sign `order`, `cancel`,
  `cancelAll`, `modify`, `tpSl`, `cancelTpSl`, `updateLeverage`. Backend
  recovers the signer, sees it's a registered agent, and routes the action
  under the master's account.

Slots per master:
  - 1 anonymous slot (no `agentName`)
  - 3 named slots (each with a distinct `agentName`)

Fields:
  - agentAddress   : the agent's wallet address (lowercase 0x…)
  - agentName      : optional; omit or empty = anonymous slot
  - validUntil     : optional ms-timestamp expiry; 0 or omitted = permanent

Usage:
  python3 examples/08_agent_delegation.py <master_priv> <agent_priv> [name] [validUntil_ms]
"""

import sys
import time

from eth_keys import keys as eth_keys_module

from common import send_exchange, info, addr_of


def _load(pk_hex):
    if pk_hex.startswith("0x"):
        pk_hex = pk_hex[2:]
    return eth_keys_module.PrivateKey(bytes.fromhex(pk_hex))


def main():
    if len(sys.argv) < 3:
        print("usage: python3 08_agent_delegation.py <master_priv_hex> <agent_priv_hex> [agentName] [validUntil_ms]")
        sys.exit(1)

    master = _load(sys.argv[1])
    agent = _load(sys.argv[2])
    agent_name = sys.argv[3] if len(sys.argv) > 3 else None
    valid_until = int(sys.argv[4]) if len(sys.argv) > 4 else None

    master_addr = addr_of(master)
    agent_addr = addr_of(agent)

    # ── approveAgent ────────────────────────────────────
    action = {"type": "approveAgent", "agentAddress": agent_addr}
    if agent_name:
        action["agentName"] = agent_name
    if valid_until is not None:
        action["validUntil"] = valid_until

    print(f"→ approveAgent master={master_addr}  agent={agent_addr}"
          f"{f' name={agent_name!r}' if agent_name else ' (anonymous slot)'}")
    code, r = send_exchange(master, action)
    print(f"  http {code}  body {r}")

    d = r.get("response", {}).get("data", {})
    if d.get("errorCode", 0) != 0:
        print(f"  ✗ approve failed: errorCode={d.get('errorCode')} {d.get('errorMessage')}")
        return

    print(f"  ✓ agent approved")
    time.sleep(1)

    # ── verify via userAgents ───────────────────────────
    # We need master's accountId; if you don't have it, run 01_register.py
    # first or ask the backend via registerAccount (it will 409 and give aid).
    code, rr = send_exchange(master, {"type": "registerAccount", "address": master_addr})
    master_aid = rr.get("response", {}).get("accountId")
    if not master_aid:
        msg = str(rr.get("message", ""))
        if "accountId=" in msg:
            master_aid = msg.split("accountId=")[-1].strip()
    print(f"\n  master accountId={master_aid}")

    if master_aid:
        ua = info({"type": "userAgents", "accountId": master_aid})
        print(f"  userAgents: {ua.get('agents')}")

    # ── demo: agent signs an order for master ───────────
    print(f"\n→ agent signs a limit order (contract=1, buy p=100 s=1)")
    code, r = send_exchange(agent, {
        "type": "order",
        "grouping": "na",
        "orders": [{
            "a": 1, "b": True, "p": "100", "s": "1",
            "r": False,
            "t": {"limit": {"tif": "Gtc"}},
        }],
    })
    print(f"  http {code}  body {r}")

    d = r.get("response", {}).get("data", {})
    if d.get("errorCode") == 30:
        print("  → errorCode:30 means the agent tried to sign a non-TRADE action.")
        print("     (Not the case here; if you see it, something is wrong.)")


if __name__ == "__main__":
    main()
