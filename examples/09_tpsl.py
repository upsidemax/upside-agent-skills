#!/usr/bin/env python3
"""
09_tpsl.py — attach a take-profit / stop-loss to an existing position.

`tpSl` binds one or two conditional orders to a position side:
  - tpPrice (optional) : take-profit trigger price
  - slPrice (optional) : stop-loss trigger price
  - positionSide       : 0 = long, 1 = short (also used for OneWay)
  - tpTriggerType/slTriggerType : 0 = last price, 1 = mark price, 2 = index price

Response returns { tpOrderId, slOrderId } for the two conditional orders.

`cancelTpSl` removes them for a given (contract, positionSide) tuple.

Pending TP/SL show up in `userOrders` with:
  - isConditional: true (or `cond: true` on some backend versions)
  - status: "Untriggered"

WS orderUpdates emit the same fields when a TP/SL is created/canceled/triggered.

Usage:
  python3 examples/09_tpsl.py <priv_key> <contractId> <tpPrice> <slPrice>
  python3 examples/09_tpsl.py cancel <priv_key> <contractId>
"""

import sys

from eth_keys import keys as eth_keys_module

from common import send_exchange


def _load(pk_hex):
    if pk_hex.startswith("0x"):
        pk_hex = pk_hex[2:]
    return eth_keys_module.PrivateKey(bytes.fromhex(pk_hex))


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)

    if sys.argv[1] == "cancel":
        pk = _load(sys.argv[2])
        contract_id = int(sys.argv[3])
        code, r = send_exchange(pk, {
            "type": "cancelTpSl", "a": contract_id, "positionSide": 0,
        })
        print(f"cancelTpSl  http {code}  body {r}")
        return

    pk = _load(sys.argv[1])
    contract_id = int(sys.argv[2])
    tp_price = sys.argv[3]
    sl_price = sys.argv[4] if len(sys.argv) > 4 else None

    action = {
        "type": "tpSl",
        "a": contract_id,
        "positionSide": 0,              # long / OneWay
        "isPositionTpsl": True,
        "tpPrice": tp_price,
        "tpTriggerType": 0,             # last price
    }
    if sl_price is not None:
        action["slPrice"] = sl_price
        action["slTriggerType"] = 0

    code, r = send_exchange(pk, action)
    d = r.get("response", {}).get("data", {})
    print(f"tpSl  http {code}")
    print(f"  tpOrderId={d.get('tpOrderId')}  slOrderId={d.get('slOrderId')}")
    if d.get("errorCode", 0) != 0:
        print(f"  ✗ errorCode={d.get('errorCode')} {d.get('errorMessage')}")


if __name__ == "__main__":
    main()
