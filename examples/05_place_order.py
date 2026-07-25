#!/usr/bin/env python3
"""
05_place_order.py — place a limit order.

Order envelope shape:
  {
    "type": "order",
    "grouping": "na",
    "orders": [
      {
        "a": <contractId int>,
        "b": <bool>,             # true=buy, false=sell
        "p": "<price string>",   # limit price (str, backend expects decimal-as-string)
        "s": "<size string>",    # order size
        "r": <bool>,             # reduce-only?
        "c": "<cloid hex>",      # optional client order id (0x + 63 hex)
        "t": {"limit": {"tif": "Gtc"}}   # or "Ioc", "Fok", "Alo"
      }
    ]
  }

`order` is fire-and-forget: backend returns 202 quickly, then the matching engine
processes asynchronously. If the contract has priceReady=false (no oracle push
yet), the engine silently drops the order — you'll see http=202 but nothing
in `userOrders`. Check `04_market_info.py` first.

Usage:
  python3 examples/05_place_order.py <private_key_hex> [contractId] [price] [size] [side]

  side: "buy" (default) or "sell"
"""

import sys

from eth_keys import keys as eth_keys_module

from common import send_exchange


def main():
    if len(sys.argv) < 2:
        print("usage: python3 05_place_order.py <private_key_hex> [contractId=1] [price=100] [size=1] [side=buy]")
        sys.exit(1)
    pk_hex = sys.argv[1]
    if pk_hex.startswith("0x"):
        pk_hex = pk_hex[2:]
    pk = eth_keys_module.PrivateKey(bytes.fromhex(pk_hex))

    contract_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    price       = sys.argv[3]       if len(sys.argv) > 3 else "100"
    size        = sys.argv[4]       if len(sys.argv) > 4 else "1"
    side        = sys.argv[5]       if len(sys.argv) > 5 else "buy"
    is_buy      = side.lower() in ("buy", "b", "long", "true")

    action = {
        "type": "order",
        "grouping": "na",
        "orders": [{
            "a": contract_id,
            "b": is_buy,
            "p": price,
            "s": size,
            "r": False,
            "t": {"limit": {"tif": "Gtc"}},
        }],
    }
    print(f"→ POST /exchange")
    print(f"   {'buy' if is_buy else 'sell'} contract={contract_id} price={price} size={size}")
    code, r = send_exchange(pk, action)
    print(f"\nhttp {code}")
    print(f"body {r}")

    if code in (200, 202):
        print(f"\n✓ order accepted at HTTP layer.")
        print(f"   Now query userOrders to confirm it entered the book:")
        print(f"     python3 examples/06_cancel_order.py list <accountId>")


if __name__ == "__main__":
    main()
