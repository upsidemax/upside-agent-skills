#!/usr/bin/env python3
"""
01_register.py — generate a fresh wallet and register it on QA.

Prints the private key so you can reuse it later. Save it somewhere safe.
On QA the private key is test-only; on any other environment do NOT print keys.

Usage:
  python3 examples/01_register.py
"""

from common import BASE_URL, INVITE_CODE, new_wallet, send_exchange, addr_of


def main():
    pk, addr = new_wallet()
    print(f"→ POST {BASE_URL}/exchange")
    print(f"  private key: 0x{pk.to_hex()[2:]}")
    print(f"  address:     {addr}")
    print(f"  alpha test invitation code: {INVITE_CODE}")

    code, r = send_exchange(pk, {
        "type": "registerAccount",
        "address": addr,
    }, invite_code=INVITE_CODE)

    print(f"\nhttp {code}")
    print(f"body {r}")

    aid = r.get("response", {}).get("accountId")
    if aid:
        print(f"\n✓ registered as accountId={aid}")
    elif r.get("code") == "ACCOUNT_ALREADY_EXISTS":
        aid = str(r.get("message", "")).split("accountId=")[-1].strip()
        print(f"\n✓ already registered as accountId={aid}")
    else:
        print(f"\n✗ registration failed")


if __name__ == "__main__":
    main()
