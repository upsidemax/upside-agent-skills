#!/usr/bin/env python3
"""
07_ws_subscribe.py — subscribe to WebSocket channels.

The WebSocket uses a JSON subscribe protocol. Send:
    {"method":"subscribe","subscription":{"type":"<channel>","<param>":"<value>"}}

Backend replies with a subscription ACK on channel "subscriptionResponse":
    {"channel":"subscriptionResponse","data":{"method":"subscribe","subscription":{…}}}

Then subsequent messages arrive on `channel: "<channel>"` with `data: {…}`.

Known channels:
  - l2Book      params: asset (contractId as str)      → order book snapshots + deltas
  - bbo         params: asset                          → best bid/offer changes
  - trades      params: asset                          → executed trades
  - candle      params: asset, interval                → candles ("1m", "5m", "1h", …)
  - config      params: (none)                         → global config change events
  - orderUpdates.<address>  → per-account order lifecycle events (fills, cancels, TP/SL triggers)

If backend responds `{"channel":"error", "data":{"code":"BAD_SUBSCRIPTION", "message":"…"}}`
you're on the wrong param name. `asset` (not `coin`, not `contractId`) is the right one.

Usage:
  python3 examples/07_ws_subscribe.py <channel_type> [--asset 1] [--duration 30]

Examples:
  python3 examples/07_ws_subscribe.py l2Book --asset 1
  python3 examples/07_ws_subscribe.py trades --asset 1 --duration 60
  python3 examples/07_ws_subscribe.py config
"""

import argparse
import json
import time

import websocket

from common import WS_URL


def build_subscription(chan, asset, interval):
    sub = {"type": chan}
    if chan in ("l2Book", "bbo", "trades"):
        sub["asset"] = asset
    if chan == "candle":
        sub["asset"] = asset
        sub["interval"] = interval
    return sub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("channel", help="l2Book | bbo | trades | candle | config | orderUpdates")
    ap.add_argument("--asset", default="1", help="contractId as string (l2Book/bbo/trades/candle only)")
    ap.add_argument("--interval", default="1m", help="candle interval, e.g. 1m/5m/1h")
    ap.add_argument("--address", default=None, help="target address (orderUpdates only)")
    ap.add_argument("--duration", type=int, default=15, help="how many seconds to listen")
    args = ap.parse_args()

    sub = build_subscription(args.channel, args.asset, args.interval)
    if args.channel == "orderUpdates":
        if not args.address:
            print("orderUpdates requires --address <0x…>")
            return
        sub = {"type": "orderUpdates", "user": args.address}

    print(f"→ WS connect  {WS_URL}")
    # Browser-style handshake headers — QA's CloudFront WAF 403s bare clients.
    ws = websocket.create_connection(
        WS_URL, timeout=8,
        header=["User-Agent: Mozilla/5.0 (upside-dex-skills)"],
        origin="https://dev.upsidemax.xyz",
    )
    payload = {"method": "subscribe", "subscription": sub}
    print(f"→ send  {json.dumps(payload)}")
    ws.send(json.dumps(payload))

    ws.settimeout(1.0)
    print(f"← listening for {args.duration}s…")
    end = time.time() + args.duration
    count = 0
    while time.time() < end:
        try:
            msg = ws.recv()
            print(f"  [{count}] {msg[:400]}")
            count += 1
        except websocket.WebSocketTimeoutException:
            continue
    ws.close()
    print(f"\n✓ received {count} message(s)")


if __name__ == "__main__":
    main()
