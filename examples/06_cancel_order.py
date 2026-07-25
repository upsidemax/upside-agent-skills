#!/usr/bin/env python3
"""
06_cancel_order.py — list & cancel orders.

Supports three sub-commands:

  list <accountId>                              — dump open orders
  cancel <priv_key> <contractId> <orderId>      — cancel one order by oid
  cancel-all <priv_key> <contractId>            — cancelAll for one contract

Usage examples:
  python3 examples/06_cancel_order.py list 5
  python3 examples/06_cancel_order.py cancel 0xabc… 1 12345
  python3 examples/06_cancel_order.py cancel-all 0xabc… 1
"""

import json
import sys

from eth_keys import keys as eth_keys_module

from common import send_exchange, info


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


def _load_pk(pk_hex):
    if pk_hex.startswith("0x"):
        pk_hex = pk_hex[2:]
    return eth_keys_module.PrivateKey(bytes.fromhex(pk_hex))


def cmd_cancel(pk_hex, contract_id, order_id):
    pk = _load_pk(pk_hex)
    print(f"→ cancel contract={contract_id} oid={order_id}")
    code, r = send_exchange(pk, {
        "type": "cancel",
        "cancels": [{"a": int(contract_id), "o": int(order_id)}],
    })
    print(f"http {code}\nbody {json.dumps(r, indent=2, ensure_ascii=False)}")


def cmd_cancel_all(pk_hex, contract_id):
    pk = _load_pk(pk_hex)
    print(f"→ cancelAll contract={contract_id}")
    code, r = send_exchange(pk, {"type": "cancelAll", "a": int(contract_id)})
    print(f"http {code}\nbody {json.dumps(r, indent=2, ensure_ascii=False)}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    sub = sys.argv[1]
    if sub == "list" and len(sys.argv) >= 3:
        cmd_list(sys.argv[2])
    elif sub == "cancel" and len(sys.argv) >= 5:
        cmd_cancel(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sub == "cancel-all" and len(sys.argv) >= 4:
        cmd_cancel_all(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
