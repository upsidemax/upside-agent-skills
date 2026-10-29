#!/usr/bin/env python3
"""
02_check_funding.py — after registering, check whether the account has margin.

A newly registered account has a zero balance on every environment and has to
be funded before it can trade. This script reads the settle-coin balance once:

  - funds at the chain level (mo=0) and as Market Deployer #1 margin (MO=1);
  - if both are zero it stops and says the account needs funding first.

Usage:
  python3 examples/02_check_funding.py [accountId]   # default: USER_ACCOUNT_ID from .env
"""

import sys

from common import FUNDING_HINT, get_balance, load_user_wallet, usdt


def main():
    aid = sys.argv[1] if len(sys.argv) > 1 else load_user_wallet()[2]
    if not aid:
        print("usage: python3 02_check_funding.py <accountId>   (or set USER_ACCOUNT_ID in .env)")
        sys.exit(1)

    mo0, mo1 = get_balance(aid)
    print(f"accountId={aid}")
    print(f"  chain level (mo=0):          {usdt(mo0)}")
    print(f"  Market Deployer #1 (MO=1):   {usdt(mo1)}")
    if mo0 == 0 and mo1 == 0:
        print(f"\n✗ {FUNDING_HINT}")
        sys.exit(2)
    if mo1 == 0:
        print("\n⚠  Funds are at the chain level only. Move them into Market Deployer #1 as margin")
        print("   (enrollUserToMarketOwner + lockCollateral) before placing orders.")
        return
    print("\n✓ Account has margin — ready to trade.")


if __name__ == "__main__":
    main()
