#!/usr/bin/env python3
"""
02_wait_airdrop.py — after registering, watch for the auto-airdrop.

On QA every new account SHOULD receive 1,000,000 USDT within ~15-30 seconds.
The airdrop lands as either:
  - mo=0 chainBalance (rare), or
  - MO=1 crossCollateral (common)

Occasionally the airdrop misses. If nothing arrives after 60s, the simplest
recovery is to re-register a fresh wallet (`python3 examples/01_register.py`)
and try again — misses tend to be per-registration, not per-service-outage.

Usage:
  python3 examples/02_wait_airdrop.py <accountId>
"""

import sys
import time

from common import get_balance, usdt


def main():
    if len(sys.argv) < 2:
        print("usage: python3 02_wait_airdrop.py <accountId>")
        sys.exit(1)
    aid = sys.argv[1]

    print(f"Watching accountId={aid} for auto-airdrop (60s, poll every 5s)")
    print(f"  {'t':>4}   {'mo=0 chainBalance':<24}   {'MO=1 crossCollateral':<24}")
    start = time.time()
    while time.time() - start < 60:
        t = time.time() - start
        mo0, mo1 = get_balance(aid)
        print(f"  {t:>4.1f}s  {usdt(mo0):<24}   {usdt(mo1):<24}")
        if mo0 > 0 or mo1 > 0:
            print(f"\n✓ Airdrop landed after {t:.1f}s")
            return
        time.sleep(5)

    print(f"\n⚠  No airdrop after 60s. Recommendations:")
    print(f"   - Simplest: run `python3 examples/01_register.py` for a fresh wallet.")
    print(f"     Airdrop misses tend to be per-registration; a fresh one usually gets it.")


if __name__ == "__main__":
    main()
