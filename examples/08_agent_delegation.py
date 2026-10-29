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

Keys come from `.env`, never the command line: the master key is
USER_PRIVATE_KEY (written by 01_register.py); the agent key is
AGENT_PRIVATE_KEY, generated and saved there on first run if missing.

Usage:
  python3 examples/08_agent_delegation.py [name] [validUntil_ms]
"""

import sys
import time

from common import ENV_PATH, info, load_agent_wallet, require_user_wallet, send_exchange


def main():
    master, master_addr, master_aid = require_user_wallet()
    had_agent = load_agent_wallet()[0] is not None
    agent, agent_addr = load_agent_wallet(create=True)
    if not had_agent:
        print(f"  new agent key saved to {ENV_PATH} (AGENT_PRIVATE_KEY, not shown)")
    agent_name = sys.argv[1] if len(sys.argv) > 1 else None
    valid_until = int(sys.argv[2]) if len(sys.argv) > 2 else None

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
    # master accountId comes from USER_ACCOUNT_ID in .env (01_register.py saves it).
    print(f"\n  master accountId={master_aid or '(USER_ACCOUNT_ID not set in .env)'}")

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
