#!/usr/bin/env python3
"""
quick_start.py — end-to-end demo of the full trading lifecycle.

Targets Mainnet (https://upsidemax.xyz) by default — real funds. Set
UPSIDE_BASE_URL=https://dev.upsidemax.xyz to run it on Devnet.

Flow:
  1. Load your wallet from `.env`, or generate one, register it (invitation
     code required) and save it to `.env` — the private key is never printed
  2. Check the balance; a new account has a zero balance, so the script stops
     here and asks you to fund the account first
  3. Place a small limit order well below the market (it rests, does not fill)
  4. Query userOrders
  5. Cancel the open order

Usage:
  python3 examples/quick_start.py
"""

import sys
import time

import requests

from common import (
    BASE_URL, FUNDING_HINT,
    new_wallet, load_user_wallet, save_wallet,
    send_exchange, info, register_account, get_balance, format_amount,
    get_contract, get_settle_coin, configs,
)

CONTRACT_ID = 1   # first contract; actual name auto-detected via /info configs


def main():
    print("=" * 60)
    print(f"UpsideMAX quick-start  →  {BASE_URL}")
    print("=" * 60)

    # ── 1. Wallet ────────────────────────────────────────
    pk, addr, aid = load_user_wallet()
    if pk:
        print(f"\n[1] Wallet from .env: {addr}")
    else:
        pk, addr = new_wallet()
        path = save_wallet(pk)
        print(f"\n[1] New wallet {addr} — private key saved to {path}")
    if not aid:
        aid = register_account(pk)
        if not aid:
            print("    ! registration failed, aborting.")
            return
        save_wallet(pk, aid)
    print(f"    accountId = {aid}")

    # ── 2. Balance ───────────────────────────────────────
    mo0, mo1 = get_balance(aid)
    print(f"\n[2] Balance:")
    print(f"    chain level (mo=0):      {format_amount(mo0)}")
    print(f"    Cross collateral (MO=1): {format_amount(mo1)}")
    if mo0 == 0 and mo1 == 0:
        print(f"\n    ✗ {FUNDING_HINT}")
        return
    if mo1 == 0:
        print("    ! no MO=1 margin — cannot place orders. Move the chain-level funds in with:")
        print("        enrollUserToMarketOwner + lockCollateral")
        return

    # ── 3. Market info ──────────────────────────────────
    contract = get_contract(CONTRACT_ID)
    settle = get_settle_coin(1)
    cname = contract["name"] if contract else f"contract #{CONTRACT_ID}"
    settle_name = settle["name"] if settle else "?"
    print(f"\n[3] Market state for contractId={CONTRACT_ID} ({cname}, settle={settle_name})")
    ms = info({"type": "marketState", "asset": str(CONTRACT_ID)})
    print(f"    markPx={ms.get('markPx')}  oraclePx={ms.get('oraclePx')}  priceReady={ms.get('priceReady')}")
    if not contract or not ms.get("priceReady"):
        print("    ⚠  contract not found or priceReady=false — pick another contract (CONTRACT_ID) and re-run.")
        return

    # ── 3. Place order ──────────────────────────────────
    # Raw integers: 20% below mark rests without filling; size is the smallest
    # whole step whose notional (price x size x notionalScaleMultiplier) reaches
    # the minimum order value.
    tick, step = int(contract["tickSize"]), int(contract["stepSize"])
    mult = int(contract["notionalScaleMultiplier"])
    price = (int(ms["markPx"]) * 80 // 100) // tick * tick
    need = -(-int(configs()["minNotionalValue"]) // (price * mult)) or 1
    PRICE, SIZE = str(price), str(-(-need // step) * step)
    print(f"\n[3] Place limit buy: contract={CONTRACT_ID} price={PRICE} size={SIZE} (raw)")
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

    # ── 4. Query userOrders ─────────────────────────────
    uo = info({"type": "userOrders", "accountId": aid, "marketDeployerId": 1, "contractId": 0})
    orders = uo.get("orders", []) or []
    print(f"\n[4] userOrders: {len(orders)} order(s)")
    for o in orders:
        print(f"    id={o.get('id')} status={o.get('status')} price={o.get('price')} size={o.get('size')} side={o.get('orderSide')}")

    # ── 5. Cancel ───────────────────────────────────────
    if orders:
        oid = int(orders[0].get("id", 0))
        print(f"\n[5] Cancel oid={oid}")
        code, r = send_exchange(pk, {"type": "cancel", "cancels": [{"a": CONTRACT_ID, "o": oid}]})
        print(f"    cancel http={code}  {r.get('response', {}).get('data', {})}")
    else:
        print(f"\n[5] Nothing to cancel — check the order response above.")

    print("\n" + "=" * 60)
    print("✓ quick_start complete")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.RequestException as e:
        print(f"\n✗ Network error reaching {BASE_URL} — it may be a temporary blip.")
        print(f"  Run this again in a moment.  ({type(e).__name__})")
        sys.exit(1)
