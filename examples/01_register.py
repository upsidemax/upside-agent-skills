#!/usr/bin/env python3
"""
01_register.py — generate a fresh wallet and register it.

Targets Mainnet (https://upsidemax.xyz) by default; set
UPSIDE_BASE_URL=https://dev.upsidemax.xyz for Devnet. Registration needs an
invitation code (UPSIDE_INVITE_CODE) on both.

The private key is saved to the gitignored `.env` (USER_PRIVATE_KEY) and is
never printed — on Mainnet it controls real funds. Later scripts pick it up
with load_user_wallet().

Usage:
  python3 examples/01_register.py
"""

import sys

from common import BASE_URL, ENV_PATH, INVITE_CODE, load_user_wallet, new_wallet, register_account, save_wallet


def main():
    existing, _, _ = load_user_wallet()
    if existing:
        print(f"✗ {ENV_PATH} already holds USER_PRIVATE_KEY — refusing to overwrite it.")
        print("  Move that key somewhere safe first if you really want a new wallet.")
        sys.exit(1)

    pk, addr = new_wallet()
    save_wallet(pk)
    print(f"→ POST {BASE_URL}/exchange")
    print(f"  address:     {addr}")
    print(f"  private key: saved to {ENV_PATH} (USER_PRIVATE_KEY)")

    aid = register_account(pk, invite_code=INVITE_CODE)
    if not aid:
        print("\n✗ registration failed")
        sys.exit(1)
    save_wallet(pk, aid)
    print(f"\n✓ registered as accountId={aid} (saved as USER_ACCOUNT_ID)")
    print("  Next: python3 examples/02_check_funding.py")


if __name__ == "__main__":
    main()
