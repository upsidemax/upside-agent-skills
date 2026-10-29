#!/usr/bin/env python3
"""
06_cancel_order.py — list & cancel orders.

Supports three sub-commands:

  list [accountId]                  — dump open orders (default: USER_ACCOUNT_ID)
  cancel <contractId> <orderId>     — cancel one order by oid
  cancel-all <contractId>           — cancelAll for one contract

The signing key is read from `.env` (USER_PRIVATE_KEY, written by
01_register.py) — never pass a private key on the command line.

Usage examples:
  python3 examples/06_cancel_order.py list
  python3 examples/06_cancel_order.py cancel 1 12345
  python3 examples/06_cancel_order.py cancel-all 1
"""

import json
import sys

from common import info, load_user_wallet, require_user_wallet, send_exchange


def cmd_list(aid):
    r = info({"type": "userOrders", "accountId": aid, "marketDeployerId": 1, "contractId": 0})
    orders = r.get("orders", []) or []
    print(f"userOrders for accountId={aid}: {len(orders)} order(s)")
    for o in orders:
        print(f"  id={o.get('id')} status={o.get('status')} contract={o.get('contractId')} "
              f"side={o.get('orderSide')} price={o.get('price')} size={o.get('size')} "
              f"cloid={o.get('cloid') or '-'}")
    if not orders:
        print("  (none)")


def cmd_cancel(contract_id, order_id):
    pk, _, _ = require_user_wallet()
    print(f"→ cancel contract={contract_id} oid={order_id}")
    code, r = send_exchange(pk, {
        "type": "cancel",
        "cancels": [{"a": int(contract_id), "o": int(order_id)}],
    })
    print(f"http {code}\nbody {json.dumps(r, indent=2, ensure_ascii=False)}")


def cmd_cancel_all(contract_id):
    pk, _, _ = require_user_wallet()
    print(f"→ cancelAll contract={contract_id}")
    code, r = send_exchange(pk, {"type": "cancelAll", "a": int(contract_id)})
    print(f"http {code}\nbody {json.dumps(r, indent=2, ensure_ascii=False)}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sub = sys.argv[1]
    if sub == "list":
        aid = sys.argv[2] if len(sys.argv) >= 3 else load_user_wallet()[2]
        if not aid:
            raise SystemExit("✗ pass an accountId or set USER_ACCOUNT_ID in .env")
        cmd_list(aid)
    elif sub == "cancel" and len(sys.argv) >= 4:
        cmd_cancel(sys.argv[2], sys.argv[3])
    elif sub == "cancel-all" and len(sys.argv) >= 3:
        cmd_cancel_all(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
