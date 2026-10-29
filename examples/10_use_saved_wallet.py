#!/usr/bin/env python3
"""
10_use_saved_wallet.py — demonstrate loading your wallet from `.env` so you
                        don't have to paste the private key on every script.

Setup once:
  python3 examples/01_register.py   # saves USER_PRIVATE_KEY / USER_ACCOUNT_ID to .env

Then any script (including this one) can pick up your identity automatically.

Usage:
  python3 examples/10_use_saved_wallet.py
"""

from common import (
    load_user_wallet, register_account, get_balance, usdt,
    send_exchange, info,
)


def main():
    pk, addr, aid = load_user_wallet()
    if not pk:
        print("✗ USER_PRIVATE_KEY not set in .env")
        print("  run: python3 examples/01_register.py  # generates a key and saves it to .env")
        return

    print(f"✓ Loaded wallet from .env")
    print(f"  address:   {addr}")
    print(f"  accountId: {aid or '(unset — will discover)'}")

    # If aid is not set, discover it via a re-registration attempt (409 gives aid).
    if not aid:
        aid = register_account(pk)
        if aid:
            print(f"  discovered accountId={aid}")
            print(f"  → save this to .env as USER_ACCOUNT_ID={aid} to skip discovery next time")
        else:
            print("  ! could not discover accountId — try 01_register.py instead")
            return

    # Show balance
    mo0, mo1 = get_balance(aid)
    print(f"\n  DexLedger (mo=0):        {usdt(mo0)}")
    print(f"  Cross collateral (MO=1): {usdt(mo1)}")

    # Show open orders (using this loaded wallet)
    uo = info({"type": "userOrders", "accountId": aid, "marketDeployerId": 1, "contractId": 0})
    orders = uo.get("orders", []) or []
    print(f"\n  Open orders: {len([o for o in orders if o.get('status') == 'Open'])}")


if __name__ == "__main__":
    main()
