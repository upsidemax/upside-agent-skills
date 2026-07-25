#!/usr/bin/env python3
"""
quick_start.py — end-to-end demo of the full trading lifecycle.

Runs entirely against QA (https://dev.upsidemax.xyz). No mainnet risk.

Flow:
  1. Generate a fresh wallet
  2. Register the account (uses the QA universal alpha test invitation code)
  3. Wait for the auto-airdrop (~10-30 seconds)
  4. Query balance and print it
  5. Place a limit order (may be silently rejected if the contract has no
     oracle price yet)
  6. Query userOrders
  7. Cancel any open order

If the airdrop doesn't arrive within 45 seconds, this script exits with a
suggestion to re-run (which generates a new wallet and tries again).

Usage:
  python3 examples/quick_start.py
"""

import sys
import time

import requests

from common import (
    BASE_URL,
    new_wallet, addr_of,
    send_exchange, info, register_account, get_balance, format_amount,
    get_contract, get_settle_coin,
)

CONTRACT_ID = 1   # first contract; actual name auto-detected via /info configs
PRICE = "100"     # limit price
SIZE = "1"        # order size (in contract's qty units)


def main():
    print("=" * 60)
    print(f"Upside quick-start  →  {BASE_URL}")
    print("=" * 60)

    # ── 1. Fresh wallet ──────────────────────────────────
    pk, addr = new_wallet()
    print(f"\n[1] Fresh wallet")
    print(f"    private key: 0x{pk.to_hex()[2:]}")
    print(f"    address:     {addr}")

    # ── 2. Register ──────────────────────────────────────
    print(f"\n[2] Register account")
    aid = register_account(pk)
    if not aid:
        print("    ! registration failed, aborting.")
        return
    print(f"    ✓ accountId = {aid}")

    # ── 3. Wait for auto-airdrop ─────────────────────────
    print(f"\n[3] Wait up to 45s for auto-airdrop…")
    got_airdrop = False
    for elapsed in range(0, 46, 3):
        mo0, mo1 = get_balance(aid)
        if mo0 > 0 or mo1 > 0:
            print(f"    ✓ funds arrived at t={elapsed}s:  mo=0 {format_amount(mo0)}, MO=1 {format_amount(mo1)}")
            got_airdrop = True
            break
        print(f"    …t={elapsed}s  (still 0)")
        time.sleep(3)

    if not got_airdrop:
        print(f"\n    ✗ No airdrop after 45s. This happens occasionally on QA.")
        print(f"      Simplest fix: re-run this script (generates a fresh wallet + tries again).")
        return

    # ── 4. Final balance ─────────────────────────────────
    mo0, mo1 = get_balance(aid)
    print(f"\n[4] Balance:")
    print(f"    DexLedger (mo=0):        {format_amount(mo0)}")
    print(f"    Cross collateral (MO=1): {format_amount(mo1)}")

    if mo1 == 0:
        print("    ! no MO=1 balance — cannot place orders.")
        print("      Your airdrop landed in mo=0 (DexLedger). Migrate via:")
        print("        enrollUserToMarketOwner + lockCollateral")
        return

    # ── 5. Market info ──────────────────────────────────
    contract = get_contract(CONTRACT_ID)
    settle = get_settle_coin(1)
    cname = contract["name"] if contract else f"contract #{CONTRACT_ID}"
    settle_name = settle["name"] if settle else "?"
    print(f"\n[5] Market state for contractId={CONTRACT_ID} ({cname}, settle={settle_name})")
    ms = info({"type": "marketState", "asset": str(CONTRACT_ID)})
    print(f"    markPx={ms.get('markPx')}  oraclePx={ms.get('oraclePx')}  priceReady={ms.get('priceReady')}")
    if not ms.get("priceReady"):
        print("    ⚠  priceReady=false — orders will be accepted (202) but silently dropped by the matching engine.")
        print("        The rest of this demo still works; it just won't produce a fill.")

    # ── 6. Place order ──────────────────────────────────
    print(f"\n[6] Place limit buy: contract={CONTRACT_ID} price={PRICE} size={SIZE}")
    code, r = send_exchange(pk, {
        "type": "order",
        "grouping": "na",
        "orders": [{
            "a": CONTRACT_ID,
            "b": True,             # true = buy
            "p": PRICE,
            "s": SIZE,
            "r": False,            # reduce-only
            "t": {"limit": {"tif": "Gtc"}},
        }],
    })
    print(f"    order http={code}  resp={r.get('status')} {r.get('response', {}).get('data', {})}")

    # give backend a moment
    time.sleep(2)

    # ── 7. Query userOrders ─────────────────────────────
    uo = info({"type": "userOrders", "accountId": aid, "marketDeployerId": 1, "contractId": 0})
    orders = uo.get("orders", []) or []
    print(f"\n[7] userOrders: {len(orders)} order(s)")
    for o in orders:
        print(f"    id={o.get('id')} status={o.get('status')} price={o.get('price')} size={o.get('size')} side={o.get('orderSide')}")

    # ── 8. Cancel ───────────────────────────────────────
    if orders:
        oid = int(orders[0].get("id", 0))
        print(f"\n[8] Cancel oid={oid}")
        code, r = send_exchange(pk, {"type": "cancel", "cancels": [{"a": CONTRACT_ID, "o": oid}]})
        print(f"    cancel http={code}  {r.get('response', {}).get('data', {})}")
    else:
        print(f"\n[8] Nothing to cancel (matching engine likely dropped the order — see priceReady above).")

    print("\n" + "=" * 60)
    print("✓ quick_start complete")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Network error reaching QA ({BASE_URL}) — it may be a temporary blip.")
        print(f"  Run this again in a moment.  ({type(e).__name__})")
        sys.exit(1)
