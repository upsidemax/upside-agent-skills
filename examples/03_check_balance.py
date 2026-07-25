#!/usr/bin/env python3
"""
03_check_balance.py — read `userAccount` and print all balance-related fields.

Two things to note:
- Account and balance queries use the `marketDeployerId` field.
- The settle coin is NOT always USDT. Depending on how the chain was
  initialized, it may be either USDC or USDT. This
  script auto-detects via `/info configs` and shows every coin the user
  holds in each layer.

Usage:
  python3 examples/03_check_balance.py <accountId>
"""

import sys

from common import (
    info, format_amount, get_all_balances, get_settle_coin, get_coin,
)


def main():
    if len(sys.argv) < 2:
        print("usage: python3 03_check_balance.py <accountId>")
        sys.exit(1)
    aid = sys.argv[1]

    settle = get_settle_coin(1)
    if settle:
        print(f"[Chain settle coin] coinId={settle['coinId']} name={settle['name']} szDecimals={settle['szDecimals']}")
    else:
        print("[Chain settle coin] configs unreachable — falling back to coinId=1")

    for layer, mdid, label in [
        ("mo=0", 0, "DexLedger (chain-level, unlocked)"),
        ("MO=1", 1, "Market #1 (locked as trading margin)"),
    ]:
        r = info({"type": "userAccount", "accountId": aid, "marketDeployerId": mdid})
        print(f"\n=== {layer}  {label} ===")
        for k in ("crossEquity", "orderFrozen", "marginAvailable",
                    "marginAvailableForOrder", "totalPositionIM", "crossPositionMM",
                    "marginShareType", "depositNonce",
                    "takerOverrideBps", "makerOverrideBps",
                    "crossCollaterals", "isolatedCollaterals", "chainBalances",
                    "positions", "portfolioGroups", "contractSettings"):
            v = r.get(k)
            if isinstance(v, list) and not v:
                v = "[]"
            print(f"  {k:<28}: {v}")

    # Human-readable summary — every coin, every layer
    all_balances = get_all_balances(aid, market_deployer_id=1)
    print(f"\n=== Summary (auto-detected coin metadata) ===")
    for label, rows in all_balances.items():
        if not rows:
            print(f"  {label}:  (empty)")
            continue
        print(f"  {label}:")
        for row in rows:
            human = int(row["raw"]) / 10**row["szDecimals"]
            print(f"    {row['name']:<6} (coinId={row['coinId']:<2}, {row['layer']}):  {human:,.4f} {row['name']}")

    # Quick settle-coin summary line for scripts / bots
    if settle:
        sc_id = settle["coinId"]
        r0 = info({"type": "userAccount", "accountId": aid, "marketDeployerId": 0})
        r1 = info({"type": "userAccount", "accountId": aid, "marketDeployerId": 1})
        mo0 = sum(int(c.get("amount", "0")) for c in (r0.get("chainBalances") or []) if c.get("coinId") == sc_id)
        mo1 = sum(int(c.get("amount", "0")) for c in (r1.get("crossCollaterals") or []) if c.get("coinId") == sc_id)
        print(f"\n=== Settle coin ({settle['name']}) totals ===")
        print(f"  DexLedger  (mo=0):        {format_amount(mo0, settle)}")
        print(f"  Margin     (MO=1):        {format_amount(mo1, settle)}")
        print(f"  Total:                    {format_amount(mo0 + mo1, settle)}")


if __name__ == "__main__":
    main()
