#!/usr/bin/env python3
"""
play.py — Upside one-command experience launcher.

A thin orchestration layer over examples/common.py. Each subcommand runs one
self-contained flow end-to-end against QA (https://dev.upsidemax.xyz) and prints
a friendly, plain-language summary — no mainnet risk, wallet keys generated at
runtime. Output is written for a person trying the product, not a debug log.

A session wallet is persisted to ~/.upside_test.json so flows chain
together: run `register` once, then `order` / `positions` / `cancel` reuse it.

Common commands:
  menu | register | full | order | close | positions | orders | cancel
  status | ws <channel> | ticker | explain <topic> | tour | export | reset

Global option:  --lang en|zh   (or env UPSIDE_LANG) for native output language.
"""

import argparse
import json
import os
import sys
import time
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

# Reuse the QA-validated helpers in examples/ (common.py imports eip712 by name,
# so the examples dir must be on sys.path).
_EXAMPLES = Path(__file__).resolve().parents[3] / "examples"
sys.path.insert(0, str(_EXAMPLES))

_DEPS = ["eth-account", "eth-keys", "eth-utils", "eth-hash[pycryptodome]", "requests", "websocket-client"]

def _ensure_deps():
    """Self-bootstrap: install the Python dependencies on first run so the skill
    works from a single command (Claude Code plugins don't run setup scripts)."""
    try:
        import eth_account, eth_keys, requests  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    print("Installing Python dependencies (first run, ~20s)…", flush=True)
    import subprocess
    # Try a normal install (works inside a venv); fall back to --user for system Python.
    for extra in ([], ["--user"]):
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *extra, *_DEPS])
        if r.returncode == 0:
            return

_ensure_deps()
try:
    import requests
    from eth_keys import keys
    from common import (
        BASE_URL, WS_URL, INVITE_CODE,
        new_wallet, send_exchange, sign_envelope, info, register_account,
        get_balance, get_all_balances, format_amount, get_contract, configs,
    )
except ModuleNotFoundError as e:
    print(f"! Could not import '{e.name}' even after installing dependencies.")
    print("  Install manually, then retry:  pip install " + " ".join(f"'{d}'" for d in _DEPS))
    sys.exit(1)

SESSION = Path.home() / ".upside_test.json"
MD = 1  # market deployer used for trading
LANG = os.environ.get("UPSIDE_LANG", "en")


def L(en, zh):
    """Pick a language variant. Keeps translations colocated with each message."""
    return zh if LANG == "zh" else en


# ── session wallet ───────────────────────────────────────────

def load_session():
    if SESSION.exists():
        try:
            return json.loads(SESSION.read_text())
        except ValueError:
            return None
    return None


def save_session(data):
    SESSION.write_text(json.dumps(data, indent=2))


def _new_session(pk, addr, aid):
    save_session({"private_key": pk.to_hex(), "address": addr, "account_id": str(aid)})


def _update_session(**kw):
    s = load_session() or {}
    s.update(kw)
    save_session(s)


def _pk_from(sess):
    h = sess["private_key"]
    return keys.PrivateKey(bytes.fromhex(h[2:] if h.startswith("0x") else h))


def _short(addr):
    return f"{addr[:6]}…{addr[-4:]}" if addr and len(addr) > 12 else addr


# ── contract picker ──────────────────────────────────────────

_PICKED = None

def pick_contract():
    """Choose a live, USDC-settled contract to demo with — prefer BTC/ETH/SOL that
    are priceReady — instead of blindly hardcoding an id that may be dormant."""
    global _PICKED
    if _PICKED:
        return _PICKED
    cts = [c for c in (configs().get("contracts") or [])
           if c.get("quoteCoinId") == 1 and c.get("status") == "Active"]
    by_name = {c["name"]: c for c in cts}
    for name in ("BTC-USDC", "ETH-USDC", "SOL-USDC"):
        c = by_name.get(name)
        if c and info({"type": "marketState", "asset": str(c["contractId"])}).get("priceReady"):
            _PICKED = (c["contractId"], c["name"])
            return _PICKED
    # fall back to the first named major, else the first active USDC contract, else id 1
    for name in ("BTC-USDC", "ETH-USDC", "SOL-USDC"):
        if name in by_name:
            _PICKED = (by_name[name]["contractId"], name)
            return _PICKED
    _PICKED = (cts[0]["contractId"], cts[0]["name"]) if cts else (1, "#1")
    return _PICKED


def _contract_name(cid):
    c = get_contract(cid)
    return c["name"] if c else f"#{cid}"


def _mark(cid):
    return int(info({"type": "marketState", "asset": str(cid)}).get("markPx") or 0)


def _best(cid):
    """Best bid / ask (raw price strings) from the REST order book, or (None, None)."""
    lb = info({"type": "l2Book", "asset": str(cid)})
    levels = lb.get("levels") or (lb.get("data") or {}).get("levels") or [[], []]
    bids, asks = (list(levels) + [[], []])[:2]
    return (bids[0]["px"] if bids else None), (asks[0]["px"] if asks else None)


# ── precision (read scales from configs; never hardcode) ─────
#
# The wire protocol is integer-only. A contract carries its own scales:
#   price_raw = display_price × 10^priceScale   (snapped to tickSize)
#   size_raw  = display_size  × 10^qtyScale     (snapped to stepSize)
# and coin amounts use the coin's own szDecimals (handled by format_amount).
# Sending a display value as-if-raw is the classic precision bug — e.g. a BTC
# "sell @ 70000" must go out as p=7000000 (priceScale=2), not 70000. Decimal
# keeps the ×10^n exact (float would drift on values like 0.1).

def _scales(cid):
    """(priceScale, qtyScale, tickSize, stepSize) for a contract, from configs.
    Falls back to the common QA shape only if configs is unreachable."""
    c = get_contract(cid) or {}
    return (int(c.get("priceScale", 2)), int(c.get("qtyScale", 4)),
            int(c.get("tickSize", 1)), int(c.get("stepSize", 1)))


def _px_to_raw(display, cid):
    ps, _, tick, _ = _scales(cid)
    raw = int((Decimal(str(display)) * (10 ** ps)).to_integral_value(rounding=ROUND_HALF_UP))
    return max(tick, raw - raw % tick)            # snap to a tickSize multiple


def _sz_to_raw(display, cid):
    _, qs, _, step = _scales(cid)
    raw = int((Decimal(str(display)) * (10 ** qs)).to_integral_value(rounding=ROUND_HALF_UP))
    return max(step, raw - raw % step)            # snap to a stepSize multiple


def _px_from_raw(raw, cid):
    if raw in (None, "", "—"):
        return "—"
    ps = _scales(cid)[0]
    return f"{Decimal(int(raw)) / (10 ** ps):,.{ps}f}"


def _sz_from_raw(raw, cid):
    if raw in (None, "", "—"):
        return "—"
    qs = _scales(cid)[1]
    s = format(Decimal(int(raw)) / (10 ** qs), 'f')
    return s.rstrip('0').rstrip('.') if '.' in s else s


# ── airdrop wait (with live countdown + one auto-retry) ──────

def _wait_airdrop(aid, timeout=45):
    for elapsed in range(0, timeout + 1, 3):
        mo0, mo1 = get_balance(aid)
        if mo1 > 0 or mo0 > 0:
            return mo0, mo1
        print(L(f"   …still waiting ({elapsed}s)", f"   …等待中（已 {elapsed}s）"))
        time.sleep(3)
    return 0, 0


def do_register(show_key=False, _retry=True):
    if not INVITE_CODE:
        print(L("✗ No alpha test invitation code set. Request one from the Upside team, then set it and retry:",
                "✗ 未设置邀请码。请向 Upside 团队索取,设置后重试:"))
        print("    export UPSIDE_INVITE_CODE=<your-code>")
        sys.exit(1)
    pk, addr = new_wallet()
    aid = register_account(pk)
    if not aid:
        print(L("✗ Registration failed. Check that QA is reachable, then retry.",
                "✗ 注册失败。请确认 QA 可访问后重试。"))
        sys.exit(1)
    print(L(f"🎉 Test account created   (wallet {_short(addr)})",
            f"🎉 测试账户已创建   （钱包 {_short(addr)}）"))
    if show_key:
        print(L(f"   private key: {pk.to_hex()}   (QA-only testnet key — no real value)",
                f"   私钥：{pk.to_hex()}   （仅 QA 测试网,无真实价值）"))
    else:
        print(L("   A throwaway QA wallet was generated and saved locally (add --show-key to reveal it).",
                "   已生成一个一次性 QA 钱包并保存在本地（加 --show-key 可显示私钥）。"))
    print(L("   Waiting for the welcome airdrop (~10-30s)…", "   正在等待欢迎空投（约 10-30 秒）…"))
    mo0, mo1 = _wait_airdrop(aid)
    if mo0 == 0 and mo1 == 0:
        if _retry:
            print(L("   ⏳ No funds yet — trying once more with a fresh wallet…",
                    "   ⏳ 还没到账 — 用新钱包再试一次…"))
            return do_register(show_key=show_key, _retry=False)
        print(L("   ⏳ Still no airdrop. This happens occasionally on QA — run `register` again in a moment.",
                "   ⏳ 仍未收到空投。QA 偶尔会这样 — 稍后再运行一次 `register`。"))
    elif mo1 > 0:
        print(L(f"💰 Funded with {format_amount(mo1)} of test money — you're ready to trade.",
                f"💰 已到账 {format_amount(mo1)} 测试金 — 可以开始交易了。"))
    else:
        print(L(f"💰 Airdrop received ({format_amount(mo0)}), but it's still in the ledger layer and not tradeable yet.",
                f"💰 已收到空投（{format_amount(mo0)}），但还在账本层、暂不可交易。"))
    _new_session(pk, addr, aid)
    return pk, addr, aid


def ensure_account(auto=True, show_key=False):
    sess = load_session()
    if sess and sess.get("account_id"):
        return _pk_from(sess), sess["address"], sess["account_id"]
    if not auto:
        return None, None, None
    return do_register(show_key=show_key)


# ── read helpers ─────────────────────────────────────────────

def _open_orders(aid):
    return info({"type": "userOrders", "accountId": str(aid),
                 "marketDeployerId": MD, "contractId": 0}).get("orders") or []


def _positions(aid):
    return info({"type": "userAccount", "accountId": str(aid),
                 "marketDeployerId": MD}).get("positions") or []


def _print_positions(aid):
    positions = _positions(aid)
    if not positions:
        print(L("Positions none open.", "持仓：无"))
        return
    print(L(f"Positions {len(positions)} open:", f"持仓 {len(positions)} 个："))
    for p in positions:
        side = L("Long", "多") if p.get("isLongPosition") else L("Short", "空")
        sz = _sz_from_raw(p.get("size"), p.get("contractId"))
        print(L(f"   {side} {sz} {_contract_name(p.get('contractId'))}"
                f"  at {p.get('leverage')}x  (unrealized PnL {p.get('unrealizedPnl')})",
                f"   {side} {sz} {_contract_name(p.get('contractId'))}"
                f"  {p.get('leverage')}x  (未实现盈亏 {p.get('unrealizedPnl')})"))


def _snapshot(aid):
    """Compact account snapshot shown after a state-changing action."""
    mo0, mo1 = get_balance(aid)
    orders = _open_orders(aid)
    positions = _positions(aid)
    print(L(f"   Account: {format_amount(mo1)} to trade · {len(orders)} open order(s) · {len(positions)} position(s)",
            f"   账户：{format_amount(mo1)} 可交易 · {len(orders)} 个挂单 · {len(positions)} 个持仓"))


# ── flows ────────────────────────────────────────────────────

# Numbered menu — the number is the selector (`play.py 1` == `play.py full`).
_MENU = [
    ("full",      "The whole trading lifecycle in ~30s   ← recommended first", "约 30 秒走完整个交易流程   ← 建议先试"),
    ("order",     "Place a trade",                                     "下一笔单"),
    ("status",    "Balance + open positions at a glance",              "一眼看余额和持仓"),
    ("positions", "Your positions + all balances",                     "持仓 + 所有余额"),
    ("orders",    "List your open orders",                             "列出你的挂单"),
    ("close",     "Close your open position(s)",                       "平掉持仓"),
    ("cancel",    "Cancel one or all open orders",                     "撤单（一个或全部）"),
    ("ws",        "Watch a live feed (l2Book / bbo / trades / candle)", "看实时行情"),
    ("ticker",    "A compact live price ticker",                       "精简的实时价格条"),
    ("explain",   "Plain explanation of a concept",                    "大白话讲解一个概念"),
    ("tour",      "Guided, narrated walkthrough",                      "带旁白的分步导览"),
    ("register",  "Create a fresh test account",                       "创建全新测试账户"),
    ("reset",     "Start over with a brand-new wallet",                "换全新钱包重来"),
]


def cmd_menu():
    sess = load_session()
    print("=" * 62)
    print(L("Upside — Test Drive   (QA testnet, no real funds)",
            "Upside — 体验场   （QA 测试网,无真实资金）"))
    print("=" * 62)
    print(L("A decentralized perpetual-futures exchange — try the whole flow in single",
            "去中心化永续合约交易所 —— 用编号一步步体验。"))
    print(L("steps. Reply with a number below (or the flow name).",
            "回复下面的编号即可（也可直接说名字）。"))
    if sess and sess.get("account_id"):
        aid = sess["account_id"]
        _, mo1 = get_balance(aid)
        print(L(f"\nSigned in as {_short(sess['address'])} · {format_amount(mo1)} to trade"
                f" · {len(_open_orders(aid))} open order(s) · {len(_positions(aid))} position(s)",
                f"\n当前钱包 {_short(sess['address'])} · {format_amount(mo1)} 可交易"
                f" · {len(_open_orders(aid))} 挂单 · {len(_positions(aid))} 持仓"))
    else:
        print(L("\nNo account yet — pick 1 (full) and it will register one for you.",
                "\n还没有账户 — 选 1（full),会帮你注册一个。"))
    print()
    for i, (name, en, zh) in enumerate(_MENU, 1):
        print(f"  {i:>2}. {name:<9} {L(en, zh)}")
    print("=" * 62)


_CONCEPTS = {
    "perp": ("Perpetual future", "永续合约",
             "A futures contract with no expiry — you hold a long/short as long as you keep margin. Price tracks the spot market via funding payments.",
             "没有到期日的期货 — 只要保证金够,多空仓可一直持有。通过资金费率让价格贴近现货。"),
    "leverage": ("Leverage", "杠杆",
             "Trade a position larger than your collateral. 10x means $100 margin controls a $1,000 position — amplifies both gains and losses.",
             "用小于仓位的保证金开更大的仓。10x 表示 100 保证金控 1000 仓位 — 盈亏同时放大。"),
    "limit": ("Limit order", "限价单",
             "An order at a price you choose. It rests in the book until the market reaches it (or you cancel).",
             "指定价格的委托,挂在盘口等市场到价成交(或被你撤销)。"),
    "market": ("Market order", "市价单",
             "Fills immediately at the best available price. Fast, but you don't control the exact price.",
             "以当前最优价立即成交。快,但不控制具体价格。"),
    "margin": ("Margin", "保证金",
             "Collateral locked to back a position. Cross margin shares one pool; isolated margin fences off a fixed amount per position.",
             "为持仓抵押的资金。全仓共用一个池;逐仓给每个仓位单独隔离固定金额。"),
    "funding": ("Funding", "资金费率",
             "Periodic payments between longs and shorts that keep the perp price near spot. Paid roughly hourly on Upside.",
             "多空之间的周期性付费,让永续价格贴近现货。Upside 大约每小时结算一次。"),
    "mark": ("Mark price", "标记价格",
             "A manipulation-resistant reference price used for PnL and liquidations — not the last trade price.",
             "用于计算盈亏和清算的抗操纵参考价 — 不是最新成交价。"),
    "tif": ("Time-in-force", "有效方式",
             "How long an order lives: Gtc (rests until filled/cancelled), Ioc (fill now, cancel the rest), Alo (post-only).",
             "订单存活方式:Gtc(挂到成交/撤销)、Ioc(立即成交剩余撤掉)、Alo(只挂单)。"),
}

def cmd_explain(topic=None):
    if not topic or topic not in _CONCEPTS:
        print(L("Explain a concept — try one of:", "解释一个概念 — 可选:"))
        print("  " + " · ".join(_CONCEPTS))
        return
    en_t, zh_t, en_d, zh_d = _CONCEPTS[topic]
    print(f"{L(en_t, zh_t)} — {L(en_d, zh_d)}")


def cmd_status():
    _, addr, aid = ensure_account(auto=False)
    if not aid:
        print(L("No account yet. Say “try it” or run `register` to start.",
                "还没有账户。说 “试试” 或运行 `register` 开始。"))
        return
    mo0, mo1 = get_balance(aid)
    print(L(f"Wallet    {_short(addr)}", f"钱包    {_short(addr)}"))
    print(L(f"Balance   {format_amount(mo1)} available to trade", f"余额   {format_amount(mo1)} 可交易"))
    if mo0 > 0:
        print(L(f"          {format_amount(mo0)} in the ledger layer (not yet tradeable)",
                f"          {format_amount(mo0)} 在账本层（暂不可交易）"))
    _print_positions(aid)


def cmd_orders():
    _, _, aid = ensure_account(auto=False)
    if not aid:
        print(L("No account yet — run `register` or `order` first.", "还没有账户 — 先运行 `register` 或 `order`。"))
        return []
    orders = _open_orders(aid)
    if not orders:
        print(L("You have no open orders.", "你没有挂单。"))
        return []
    print(L(f"You have {len(orders)} open order(s):", f"你有 {len(orders)} 个挂单："))
    for o in orders:
        verb = L("Buy", "买") if o.get("orderSide") == "B" else L("Sell", "卖")
        cid = o.get("contractId")
        print(f"   #{o.get('id')}  {verb} {_sz_from_raw(o.get('size'), cid)} {_contract_name(cid)}"
              f" @ {_px_from_raw(o.get('price'), cid)}  ({o.get('status')})")
    return orders


def cmd_positions():
    _, _, aid = ensure_account(auto=False)
    if not aid:
        print(L("No account yet — run `register` first.", "还没有账户 — 先运行 `register`。"))
        return
    _print_positions(aid)
    tradeable = get_all_balances(aid).get(f"MO={MD}", [])
    if tradeable:
        print(L("Balances  ", "余额  ") + ", ".join(format_amount(r["raw"], r) for r in tradeable))


def _print_code(action, aid_pk):
    """Show the exact signed request that performed an action (idea: bridge to integration)."""
    env = sign_envelope(aid_pk, dict(action))
    print(L("\n   ── the signed request that did this (POST /exchange) ──",
            "\n   ── 刚才这笔操作的签名请求（POST /exchange）──"))
    print("   " + json.dumps(env, separators=(",", ":"))[:600])
    print(L("   Reproduce it: examples/common.py → send_exchange(pk, action). See examples/05_place_order.py.",
            "   复现方式:examples/common.py → send_exchange(pk, action)。参考 examples/05_place_order.py。"))


def cmd_order(side="buy", price=None, size="1", contract=None, tif="Gtc", show_key=False,
              show_code=False, again=False):
    pk, _, aid = ensure_account(show_key=show_key)
    if again:
        last = (load_session() or {}).get("last_order")
        if last:
            side, price, size, contract, tif = (last["side"], last["price"], last["size"],
                                                last["contract"], last["tif"])
    if contract is None:
        contract, _ = pick_contract()
    cname = _contract_name(contract)
    verb = L("Buy", "买") if side == "buy" else L("Sell", "卖")
    is_market = price is None   # no explicit price → a market (current-price) order
    if is_market:
        order_obj = {"a": contract, "b": side == "buy", "s": str(_sz_to_raw(size, contract)),
                     "r": False, "t": {"market": {}}}
        pricetxt = L("at market", "市价")
    else:
        order_obj = {"a": contract, "b": side == "buy",
                     "p": str(_px_to_raw(price, contract)), "s": str(_sz_to_raw(size, contract)),
                     "r": False, "t": {"limit": {"tif": tif}}}
        pricetxt = f"@ {price}"
    before = len(_positions(aid))
    action = {"type": "order", "grouping": "na", "orders": [order_obj]}
    code, r = send_exchange(pk, dict(action))
    if not (r.get("status") == "accepted" or (r.get("status") == "ok" and code < 300)):
        reason = r.get("message") or r.get("response", {}).get("data", {}) or f"HTTP {code}"
        print(L(f"✗ Order not accepted: {reason}", f"✗ 订单未被接受：{reason}"))
        return
    _update_session(last_order={"side": side, "price": price, "size": str(size),
                                "contract": contract, "tif": tif})
    print(L(f"✓ Order submitted:  {verb} {size} {cname} {pricetxt}",
            f"✓ 已提交：{verb} {size} {cname} {pricetxt}"))
    time.sleep(2)
    if len(_positions(aid)) > before:
        print(L("🎯 Filled — you now hold a position:", "🎯 已成交 — 你现在有一个持仓："))
        _print_positions(aid)
        print(L("   Close it anytime — pick `close` from the menu.", "   随时可平 —— 从菜单选 `close`。"))
    elif is_market:
        print(L("   The book is thin right now, so it didn't fill — and a market order leaves nothing "
                "resting. It fills instantly when there's depth; to rest an order, use `order --price <n>`.",
                "   当前盘口较薄,未成交 —— 市价单也不会留下挂单。有深度时会立即成交;想挂单用 `order --price <价>`。"))
    else:
        orders = _open_orders(aid)
        if orders:
            print(L(f"   Resting as order #{orders[-1].get('id')} @ {price} — it'll fill when the market reaches it.",
                    f"   已挂为订单 #{orders[-1].get('id')} @ {price} —— 到价即成交。"))
    if show_code:
        _print_code(action, pk)
    _snapshot(aid)


def cmd_close():
    _, _, aid = ensure_account(auto=False)
    if not aid:
        print(L("No account yet.", "还没有账户。"))
        return
    positions = _positions(aid)
    if not positions:
        print(L("You have no open positions to close.", "你没有可平的持仓。"))
        return
    pk = _pk_from(load_session())
    for p in positions:
        cid = p.get("contractId")
        is_long = p.get("isLongPosition")
        mark = _mark(cid) or 100
        # opposite, marketable, reduce-only
        close_price = str(max(1, mark // 2)) if is_long else str(mark * 2)
        r = send_exchange(pk, {"type": "order", "grouping": "na",
                               "orders": [{"a": cid, "b": not is_long, "p": close_price,
                                           "s": str(p.get("size")), "r": True,
                                           "t": {"limit": {"tif": "Ioc"}}}]})[1]
        ok = r.get("status") in ("accepted", "ok")
        print(L(f"{'✓ Sent close for' if ok else '✗ Could not close'} your {_contract_name(cid)} position",
                f"{'✓ 已发送平仓' if ok else '✗ 无法平仓'}：{_contract_name(cid)}"))
    time.sleep(2)
    remaining = _positions(aid)
    print(L(f"Positions now open: {len(remaining)}", f"当前剩余持仓：{len(remaining)}")
          + (L("  (QA liquidity is thin, so a close may rest instead of filling)",
               "  （QA 流动性较薄,平仓可能只是挂住而未成交）") if remaining else ""))
    _snapshot(aid)


def cmd_cancel(oid=None, cancel_all=False):
    _, _, aid = ensure_account(auto=False)
    if not aid:
        print(L("No account yet.", "还没有账户。"))
        return
    pk = _pk_from(load_session())
    orders = _open_orders(aid)
    if not orders:
        print(L("Nothing to cancel — you have no open orders.", "没有可撤的挂单。"))
        return
    if cancel_all:
        targets = orders
    elif oid is not None:
        targets = [o for o in orders if str(o.get("id")) == str(oid)]
    else:
        targets = orders[:1]
    if not targets:
        print(L(f"No open order #{oid}.", f"没有编号为 #{oid} 的挂单。"))
        return
    for o in targets:
        r = send_exchange(pk, {"type": "cancel",
                               "cancels": [{"a": o.get("contractId", 1), "o": int(o.get("id"))}]})[1]
        ok = r.get("status") in ("accepted", "ok")
        print(L(f"{'✓ Cancelled' if ok else '✗ Could not cancel'} order #{o.get('id')}",
                f"{'✓ 已撤销' if ok else '✗ 无法撤销'}订单 #{o.get('id')}"))
    _snapshot(aid)


# ── live market (pretty-printed) ─────────────────────────────

_WS_CID = None   # contract being streamed — lets _fmt_ws scale px/sz for display

def _fmt_ws(msg):
    try:
        d = json.loads(msg)
    except ValueError:
        return f"  • {msg[:220]}"
    ch, data = d.get("channel"), d.get("data")
    if ch == "subscriptionResponse":
        return L("  ✓ subscription confirmed, waiting for updates…", "  ✓ 订阅成功,等待更新…")
    if ch == "error":
        return f"  ✗ {data}"
    if ch == "l2Book" and isinstance(data, dict):
        bids, asks = (data.get("levels") or [[], []])[:2] if len(data.get("levels") or []) == 2 else ([], [])
        bb = f"{_px_from_raw(bids[0]['px'], _WS_CID)}×{_sz_from_raw(bids[0]['sz'], _WS_CID)}" if bids else "—"
        ba = f"{_px_from_raw(asks[0]['px'], _WS_CID)}×{_sz_from_raw(asks[0]['sz'], _WS_CID)}" if asks else "—"
        return f"  📖 mark {_px_from_raw(data.get('markPx'), _WS_CID)} | bid {bb} / ask {ba} | {len(bids)} bid / {len(asks)} ask levels"
    if ch == "trades" and isinstance(data, list):
        out = []
        for t in data:
            arrow = "🟢" + L("BUY", "买") if t.get("side") == "B" else "🔴" + L("SELL", "卖")
            out.append(f"  {arrow} {_sz_from_raw(t.get('sz'), _WS_CID)} @ {_px_from_raw(t.get('px'), _WS_CID)}")
        return "\n".join(out) if out else "  • (no trades)"
    if ch == "candle" and isinstance(data, dict):
        return (f"  🕯 {data.get('interval')}  O{_px_from_raw(data.get('open'), _WS_CID)} "
                f"H{_px_from_raw(data.get('high'), _WS_CID)} L{_px_from_raw(data.get('low'), _WS_CID)} "
                f"C{_px_from_raw(data.get('close'), _WS_CID)}  vol {data.get('volume')}")
    if ch == "orderUpdates" and isinstance(data, list):
        out = []
        for o in data:
            side = L("buy", "买") if o.get("side") == "B" else L("sell", "卖")
            out.append(f"  🔔 order #{o.get('oid')} {side} {_sz_from_raw(o.get('sz'), _WS_CID)} "
                       f"@ {_px_from_raw(o.get('px'), _WS_CID)} ({o.get('st')})")
        return "\n".join(out)
    if ch == "config" and isinstance(data, dict):
        return f"  ⚙ {data.get('eventType')} {({k: v for k, v in data.items() if k != 'eventType'})}"
    return f"  • {ch}: {json.dumps(data)[:200]}"


def _stream(sub, duration, on_msg):
    import websocket
    try:
        ws = websocket.create_connection(
            WS_URL, timeout=8,
            header=["User-Agent: Mozilla/5.0 (upside-upside-test)"],
            origin="https://dev.upsidemax.xyz")
    except Exception as e:
        print(L(f"✗ Couldn't open the live feed: {type(e).__name__}: {str(e)[:120]}",
                f"✗ 无法打开实时行情：{type(e).__name__}: {str(e)[:120]}"))
        print(L("  QA's stream sits behind CloudFront and may block non-browser clients. Retry in a moment.",
                "  QA 行情在 CloudFront 后面,可能拦截非浏览器客户端。稍后重试。"))
        return 0
    n = 0
    try:
        ws.send(json.dumps({"method": "subscribe", "subscription": sub}))
        ws.settimeout(1.0)
        end = time.time() + duration
        while time.time() < end:
            try:
                n += on_msg(ws.recv())
            except websocket.WebSocketTimeoutException:
                continue
    finally:
        ws.close()
    return n


def cmd_ws(channel, asset="1", interval="1m", duration=15):
    global _WS_CID
    _WS_CID = int(asset) if str(asset).isdigit() else None
    sub = {"type": channel}
    if channel in ("l2Book", "bbo", "trades", "candle"):
        sub["asset"] = str(asset)
    if channel == "candle":
        sub["interval"] = interval
    who = _contract_name(int(asset)) if str(asset).isdigit() else asset
    print(L(f"Connecting to the live {channel} feed for {who}…", f"正在连接 {who} 的实时 {channel} 行情…"))

    def on_msg(msg):
        line = _fmt_ws(msg)
        print(line)
        return 0 if ("✓" in line or "•" in line and channel not in ("trades",)) else 1
    print(L(f"Streaming for {duration}s (Ctrl-C to stop):", f"接收 {duration} 秒（Ctrl-C 停止）:"))
    n = _stream(sub, duration, on_msg)
    print(L(f"Done — {n} update(s) in {duration}s", f"结束 — {duration} 秒内 {n} 条更新")
          + (L("  (quiet market — try again during active trading)", "  （行情清淡 — 交易活跃时再试）") if n == 0 else ""))


def cmd_ticker(contract=None, duration=15):
    if contract is None:
        contract, _ = pick_contract()
    cname = _contract_name(contract)
    print(L(f"Live price for {cname} ({duration}s):", f"{cname} 实时价（{duration}s）:"))

    def on_msg(msg):
        try:
            d = json.loads(msg).get("data") or {}
        except ValueError:
            return 0
        if "markPx" not in d:
            return 0
        levels = d.get("levels") or [[], []]
        bids, asks = (levels + [[], []])[:2]
        mark = _px_from_raw(d.get("markPx"), contract)
        bb = _px_from_raw(bids[0]["px"], contract) if bids else "—"
        ba = _px_from_raw(asks[0]["px"], contract) if asks else "—"
        print(L(f"  {cname}  mark {mark}  bid {bb} / ask {ba}",
                f"  {cname}  标记 {mark}  买 {bb} / 卖 {ba}"))
        return 1
    _stream({"type": "l2Book", "asset": str(contract)}, duration, on_msg)


def cmd_tour():
    print(L("Guided tour — I'll narrate each step of a real (test) trading session.\n",
            "导览 — 我会为一次真实（测试）交易的每一步做讲解。\n"))
    steps = [
        (L("1) Your identity is a wallet. No email, no password — a keypair signs every request.",
           "1) 你的身份就是一个钱包。没有邮箱密码 — 用密钥对给每个请求签名。")),
        (L("2) Registering mints you free test USDC on the QA network so you can trade risk-free.",
           "2) 注册会在 QA 网络给你铸造免费测试 USDC,可零风险交易。")),
        (L("3) An order says: buy/sell how much, at what price. It rests until the market meets it.",
           "3) 一笔订单表达:买/卖多少、什么价。它会挂着直到市场到价。")),
        (L("4) A fill opens a position; its value moves with the mark price (your PnL).",
           "4) 成交后开出持仓;其价值随标记价波动(就是你的盈亏)。")),
        (L("5) You close by trading the opposite side. Cancel removes an unfilled order.",
           "5) 反向交易即可平仓。撤单则移除未成交的委托。")),
    ]
    for s in steps:
        print(s)
    print(L("\nNow running it for real:\n", "\n现在真跑一遍:\n"))
    cmd_full()


def cmd_full(contract=None, price=None, size="1", show_key=False):
    print(L("Running the full experience: create account → get test money → trade at market.\n",
            "运行完整体验:创建账户 → 领测试金 → 市价下单。\n"))
    _, _, aid = ensure_account(show_key=show_key)
    _, mo1 = get_balance(aid)
    if mo1 == 0:
        print(L("\nFunds aren't tradeable yet — try `status` again in a few seconds.",
                "\n资金暂不可交易 — 几秒后再 `status` 看看。"))
        return
    if contract is None:
        contract, _ = pick_contract()
    print()
    # A market order at the current price: it fills instantly when the book has depth
    # (→ a real position), and leaves nothing resting when it doesn't — no lowball, no cancel.
    cmd_order(side="buy", price=price, size=size, contract=contract)
    print(L("\n✓ That's the flow — account, funds, and a trade at the current price."
            " If it opened a position, pick `close` from the menu when you're done.",
            "\n✓ 这就是流程 — 账户、资金、一笔现价单。若开了仓,完事后从菜单选 `close` 平仓即可。"))


def cmd_export(path=None):
    sess = load_session()
    if not sess or not sess.get("account_id"):
        print(L("No session to export — run `register` first.", "没有可导出的会话 — 先 `register`。"))
        return
    dest = Path(path) if path else (_EXAMPLES.parent / ".env")
    dest.write_text(
        f"USER_PRIVATE_KEY={sess['private_key']}\n"
        f"USER_ACCOUNT_ID={sess['account_id']}\n")
    print(L(f"✓ Wrote {dest}", f"✓ 已写入 {dest}"))
    print(L("  The examples/ scripts now load this account via common.load_user_wallet().",
            "  examples/ 脚本现在会通过 common.load_user_wallet() 使用这个账户。"))
    print(L("  Try: python3 examples/03_check_balance.py", "  试试:python3 examples/03_check_balance.py"))


def cmd_reset():
    if SESSION.exists():
        SESSION.unlink()
        print(L("Done — the saved wallet was forgotten. The next flow starts fresh.",
                "完成 — 已清除保存的钱包。下一个流程从头开始。"))
    else:
        print(L("Nothing to reset — no saved wallet.", "无需重置 — 没有保存的钱包。"))


# ── next-step nudges ─────────────────────────────────────────

_NUDGES = {
    "register": ("place your first trade with `order`, or run `full` for the whole lifecycle.",
                 "用 `order` 下第一笔单,或 `full` 走完整流程。"),
    "order": ("`orders` to review it, `close`/`cancel` to exit, or `positions` to see your account.",
              "`orders` 查看,`close`/`cancel` 退出,或 `positions` 看账户。"),
    "close": ("`order` to trade again, or `status` to confirm you're flat.",
              "`order` 再交易,或 `status` 确认已平。"),
    "cancel": ("`order` to trade again, or `ws trades` to watch the live market.",
               "`order` 再交易,或 `ws trades` 看实时行情。"),
    "status": ("`order` to place a trade, or `ticker` for a live price.",
               "`order` 下单,或 `ticker` 看实时价。"),
    "reset": ("`register` or `full` to start a fresh run.", "`register` 或 `full` 重新开始。"),
    "full": ("`ws trades` for a live feed, `explain leverage` to learn more, or `order` to trade again.",
             "`ws trades` 看实时行情,`explain leverage` 了解更多,或 `order` 再交易。"),
}


# ── dispatch ─────────────────────────────────────────────────

def main():
    global LANG
    # `--lang` may appear anywhere (before OR after the subcommand). argparse only
    # accepts a global option *before* the subcommand, so pull it out ourselves
    # first — this makes `order --side sell --lang zh` work too.
    argv = sys.argv[1:]
    cleaned = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--lang" and i + 1 < len(argv):
            LANG = argv[i + 1]; i += 2; continue
        if a.startswith("--lang="):
            LANG = a.split("=", 1)[1]; i += 1; continue
        cleaned.append(a); i += 1
    argv = cleaned

    # Menu-number selection: `play.py 1` -> the 1st menu flow, etc.
    if argv and argv[0].isdigit():
        n = int(argv[0])
        if 1 <= n <= len(_MENU):
            argv[0] = _MENU[n - 1][0]
    sys.argv = [sys.argv[0]] + argv

    ap = argparse.ArgumentParser(description="Upside experience test drive")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("menu")
    p_reg = sub.add_parser("register"); p_reg.add_argument("--show-key", action="store_true")
    sub.add_parser("status")
    sub.add_parser("positions")
    sub.add_parser("orders")
    sub.add_parser("close")
    sub.add_parser("reset")

    p_order = sub.add_parser("order")
    p_order.add_argument("--side", choices=["buy", "sell"], default="buy")
    p_order.add_argument("--price", default=None)
    p_order.add_argument("--size", default="1")
    p_order.add_argument("--contract", type=int, default=None)
    p_order.add_argument("--tif", default="Gtc")
    p_order.add_argument("--show-code", action="store_true")
    p_order.add_argument("--again", action="store_true")

    p_cancel = sub.add_parser("cancel")
    p_cancel.add_argument("--oid", default=None)
    p_cancel.add_argument("--all", action="store_true")

    p_ws = sub.add_parser("ws")
    p_ws.add_argument("channel", help="l2Book | bbo | trades | candle | config")
    p_ws.add_argument("--asset", default="1")
    p_ws.add_argument("--interval", default="1m")
    p_ws.add_argument("--duration", type=int, default=15)

    p_tick = sub.add_parser("ticker")
    p_tick.add_argument("--contract", type=int, default=None)
    p_tick.add_argument("--duration", type=int, default=15)

    p_exp = sub.add_parser("explain"); p_exp.add_argument("topic", nargs="?")
    sub.add_parser("tour")

    p_full = sub.add_parser("full")
    p_full.add_argument("--contract", type=int, default=None)
    p_full.add_argument("--price", default=None)
    p_full.add_argument("--size", default="1")
    p_full.add_argument("--show-key", action="store_true")

    p_export = sub.add_parser("export"); p_export.add_argument("--path", default=None)

    args = ap.parse_args()
    cmd = args.cmd or "menu"

    if cmd == "menu":
        cmd_menu()
    elif cmd == "register":
        do_register(show_key=args.show_key)
    elif cmd == "status":
        cmd_status()
    elif cmd == "positions":
        cmd_positions()
    elif cmd == "orders":
        cmd_orders()
    elif cmd == "close":
        cmd_close()
    elif cmd == "reset":
        cmd_reset()
    elif cmd == "order":
        cmd_order(args.side, args.price, args.size, args.contract, args.tif,
                  show_code=args.show_code, again=args.again)
    elif cmd == "cancel":
        cmd_cancel(oid=args.oid, cancel_all=args.all)
    elif cmd == "ws":
        cmd_ws(args.channel, args.asset, args.interval, args.duration)
    elif cmd == "ticker":
        cmd_ticker(args.contract, args.duration)
    elif cmd == "explain":
        cmd_explain(args.topic)
    elif cmd == "tour":
        cmd_tour()
    elif cmd == "full":
        cmd_full(args.contract, args.price, args.size, show_key=args.show_key)
    elif cmd == "export":
        cmd_export(args.path)

    if cmd in _NUDGES:
        print("\n→ " + L("Next: " + _NUDGES[cmd][0], "下一步:" + _NUDGES[cmd][1]))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(L("\n(stopped)", "\n(已停止)"))
    except requests.exceptions.RequestException as e:
        print(L(f"\n✗ Couldn't reach the QA server at {BASE_URL}. Check your connection and retry.",
                f"\n✗ 无法连接 QA 服务器 {BASE_URL}。请检查网络后重试。") + f"  ({type(e).__name__})")
        sys.exit(1)
