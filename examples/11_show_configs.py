#!/usr/bin/env python3
"""
11_show_configs.py — dump the chain's live config: which coins exist, which
                      contracts exist, which coin is the settle coin per
                      market deployer.

This is the source of truth for "what settle coin does this environment use?"
It's used implicitly by common.get_settle_coin() and get_balance().

/info configs works without signing (read-only).

Usage:
  python3 examples/11_show_configs.py
"""

import sys

from common import configs, get_settle_coin


def main():
    cfg = configs(force_refresh=True)
    if cfg.get("type") != "configs":
        print(f"✗ /info configs unreachable or unexpected response: {cfg}")
        sys.exit(1)

    coins = cfg.get("coins") or []
    mds = cfg.get("marketDeployers") or []
    contracts = cfg.get("contracts") or []

    print(f"=== Coins ({len(coins)}) ===")
    print(f"  {'coinId':>6}  {'name':<8}  {'szDecimals':>10}  {'isMargin':>8}  status")
    for c in sorted(coins, key=lambda x: x.get("coinId", 0)):
        print(f"  {c.get('coinId',''):>6}  {c.get('name',''):<8}  {c.get('szDecimals',''):>10}"
              f"  {str(c.get('isMargin','')):>8}  {c.get('status','')}")

    print(f"\n=== Market Deployers ({len(mds)}) ===")
    coins_by_id = {c["coinId"]: c for c in coins}
    for md in mds:
        sc = coins_by_id.get(md.get("settleCoinId"))
        sc_str = f"{sc['name']} (coinId={sc['coinId']})" if sc else f"coinId={md.get('settleCoinId')}"
        print(f"  MD={md.get('marketDeployerId')}  settle={sc_str}"
              f"  deployerAid={md.get('deployerAccountId')}  liquidatorAid={md.get('liquidatorAccountId')}"
              f"  taker/maker bps={md.get('deployerTakerBps')}/{md.get('deployerMakerBps')}")

    print(f"\n=== Contracts ({len(contracts)}) ===")
    print(f"  {'cid':>4}  {'name':<20}  {'base':>4}  {'quote':>5}  {'priceScale':>10}  {'qtyScale':>8}"
          f"  {'lev':>3}  {'status':<8}")
    for c in sorted(contracts, key=lambda x: x.get("contractId", 0)):
        base = coins_by_id.get(c.get("baseCoinId"))
        quote = coins_by_id.get(c.get("quoteCoinId"))
        print(f"  {c.get('contractId',''):>4}  {c.get('name',''):<20}"
              f"  {base['name'] if base else '?':>4}  {quote['name'] if quote else '?':>5}"
              f"  {c.get('priceScale',''):>10}  {c.get('qtyScale',''):>8}"
              f"  {c.get('defaultLeverage',''):>3}  {c.get('status',''):<8}")

    # Quick reference — the most important line for skill callers
    settle = get_settle_coin(1)
    if settle:
        print(f"\n👉 MO=1 settle coin: coinId={settle['coinId']} name={settle['name']}"
              f" szDecimals={settle['szDecimals']}")


if __name__ == "__main__":
    main()
