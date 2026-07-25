#!/usr/bin/env python3
"""
04_market_info.py — look up market state and order book for a contract.

Two info types:
  - marketState : point-in-time price + funding info for one contract
  - l2Book      : current bid/ask levels

Both take `asset` (the contractId as a string).

Usage:
  python3 examples/04_market_info.py [contractId]

Default contractId = 1.
"""

import json
import sys

from common import info, get_contract, get_coin


def main():
    contract_id = sys.argv[1] if len(sys.argv) > 1 else "1"

    contract = get_contract(int(contract_id))
    if contract:
        base = get_coin(contract.get("baseCoinId"))
        quote = get_coin(contract.get("quoteCoinId"))
        base_name = base["name"] if base else f"coinId={contract.get('baseCoinId')}"
        quote_name = quote["name"] if quote else f"coinId={contract.get('quoteCoinId')}"
        print(f"=== contract {contract_id}: {contract.get('name')} ({base_name}/{quote_name}) ===")
        print(f"  priceScale={contract.get('priceScale')} qtyScale={contract.get('qtyScale')}"
              f"  tickSize={contract.get('tickSize')} stepSize={contract.get('stepSize')}"
              f"  defaultLeverage={contract.get('defaultLeverage')}")
        print()
    else:
        print(f"⚠  contract {contract_id} not found in /info configs (may be a dummy asset ID)")
        print()

    ms = info({"type": "marketState", "asset": contract_id})
    print(f"=== marketState asset={contract_id} ===")
    print(json.dumps(ms, indent=2, ensure_ascii=False))
    print()

    ready = ms.get("priceReady")
    if not ready:
        print("⚠  priceReady=false. This contract has no oracle price yet.")
        print("   Orders will still receive http=202 (accepted) but the matching")
        print("   engine will silently drop them because price-band validation fails.")
        print()

    l2 = info({"type": "l2Book", "asset": contract_id})
    print(f"=== l2Book asset={contract_id} ===")
    print(json.dumps(l2, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
