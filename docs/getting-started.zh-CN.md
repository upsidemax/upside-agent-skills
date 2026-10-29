# 快速上手（中文）

本指南带您从零完成注册到下第一单，无需任何 DEX 使用经验。

**概要** — 一行命令：
```bash
./install.sh && python3 examples/quick_start.py
```
以上即为完整流程。若想了解每一步的作用，请继续阅读下文。

---

## Upside 是什么

一个去中心化的永续合约交易所（perpetual futures DEX）。你用一种稳定币（结算币，从 `configs` 读取）做保证金，可以做多或做空 `BTC-USDC`、`ETH-USDC` 等合约。每次操作（充值、下单、撤单）都是由钱包地址签名发起的请求 —— 没有用户名密码。

**当前部署到底用哪个币？** 查 `/info configs` —— 看 `marketDeployers[0].settleCoinId`，再在 `coins[]` 找到对应名字。跑 `examples/11_show_configs.py` 一次即可看到完整快照。

签名采用 **EIP-712** + secp256k1（与以太坊相同的底层原语），domain 为 `{name:"Exchange", version:"1", chainId}`，chainId 随环境而定。

| 环境 | 端点 | chainId | |
|---|---|---|---|
| **主网 Mainnet**（默认） | `https://upsidemax.xyz` | `9788` | 真实资金 |
| Devnet | `https://dev.upsidemax.xyz` | `9767` | 测试用 —— 设 `UPSIDE_BASE_URL` |

两个环境注册都需要邀请码。新账户余额为 0，注资后才能交易。

## 前置要求

- Python 3.9+（`python3 --version` 检查）
- `pip`（`python3 -m pip --version`）

就这些。不需要钱包软件、不需要浏览器插件。

## 安装

```bash
git clone https://github.com/upsidemax/upside-agent-skills.git
cd upside-agent-skills
./install.sh
```

安装 4 个 Python 包（`eth-keys`、`eth-utils`、`requests`、`websocket-client`）。若 `pip` 失败，用 venv：
```bash
python3 -m venv .venv && source .venv/bin/activate && ./install.sh
```

## 下单前需要了解的 5 个概念

下单前请先理解以下概念，它们会贯穿整个 API。

### 1. 钱包地址 vs accountId

- **地址**（address）是 42 字符 hex 字符串（`0xabc…`），由私钥推导。和以太坊地址完全一样。
- **accountId**（简称 `aid`）是后端第一次注册时分配的小整数（`5`、`12`、`100`）。一旦注册，地址和 aid 一一对应，永久不变。

大部分 API 查询用 `accountId`，不用地址。注册一次拿到 aid 存好即可。

### 2. 两层余额：mo=0 vs MO=1

每个账户在**两个地方**都有余额：

| 层 | 名字 | 能下单吗？ |
|---|---|:---:|
| `mo=0` | **DexLedger**（链上通用账本） | ❌ |
| `MO=1` | **Market #1**（锁作合约保证金） | ✅ |

从 `mo=0 → MO=1`：先 `enrollUserToMarketOwner`，再 `lockCollateral`。

类比：`mo=0` 是你的银行账户；`MO=1` 是你转到券商保证金账户里的钱。

### 3. Contract vs coin

- **Coin**（`coinId`）：币种。不同环境编号不同，**不要硬编码**，用 `/info configs` 里的 `marketDeployers[0].settleCoinId` 决定。
- **Contract**（`contractId`）：可交易的合约对（如 `BTC-USDC`）。不同环境编号不同，名字来源 `/info configs.contracts[].name`。

你交易 `contract`，盈亏结算到 `settleCoin`（由链上声明的那个币）。**不要混淆 `coinId` 和 `contractId`** —— 它们是两套独立编号。

### 4. Master vs Agent

每个账户有一个 **master 私钥**（完整权限：交易 / 存取款 / 授权 agent）。

master 可选地授权最多 4 把 **agent 私钥**（1 个匿名 + 3 个具名）。agent 能替 master 交易，但**不能**存取款或授权其他 agent。适合部署机器人：master 离线保管，agent 挂在服务器上跑。

第一次用不需要 agent，master 一把钥匙就能完成全部操作。

### 5. EIP-712 签名

每个写请求（register / order / cancel / …）都用 EIP-712 签名。两条路径，按 `action.type` 自动路由：

- **Typed path**：账户类动作（`registerAccount`、`approveAgent`、`revokeAgent`、`lockCollateral`、`unlockCollateral`、`transferBetweenDeployers`）—— 每个有自己的 typed struct。
- **Agent path**：交易类动作（`order`、`cancel`、`modify`、`tpSl`、`updateLeverage` 等）—— 整个 action 的 canonical JSON 会被包成一个 `actionHash`，装进 `Agent(string source, bytes32 actionHash)` 包装里签。

Domain：`{name: "Exchange", version: "1", chainId, verifyingContract: 0x0}` —— 主网 chainId `9788`，Devnet `9767`，两条路径都用它。

`examples/common.py` 都封装好了。除非要用别的语言写客户端，否则不用碰底层签名 —— 完整 spec + 参考实现见 [../skills/upside-onboarding/_shared/signing.md](../skills/upside-onboarding/_shared/signing.md)。

## 第 1 步：注册账户

```bash
python3 examples/01_register.py
```

输出：
```
→ POST https://upsidemax.xyz/exchange
  address:     0xbc441092113fc1ccb2a6197f095c11e730070fed
  private key: saved to …/.env (USER_PRIVATE_KEY)

✓ registered as accountId=26 (saved as USER_ACCOUNT_ID)
```

私钥写进被 gitignore 的 `.env`（权限 600），**不会打印出来** —— 主网上它控制的是真实资金。请自行备份这个文件；其他示例脚本会从这里读取。

### 为什么需要邀请码？

主网和 Devnet 注册都需要邀请码。请向 Upside 团队申请，并通过 `UPSIDE_INVITE_CODE` 环境变量设置。邀请码放在 envelope 层（**不是** action 里）；`common.py` 会自动处理。

## 第 2 步：为账户注资

新注册的账户余额为 **0** —— 任何环境都不会自动到账。交易前请先为账户注资（注资方式请联系 Upside 团队），然后检查：

```bash
python3 examples/02_check_funding.py      # 默认用 .env 里的 USER_ACCOUNT_ID
```

脚本只查一次余额，仍为 0 时会明确提示。raw 金额换算：`human = raw / 10**szDecimals`（`szDecimals` 从 `configs` 读取）。

## 第 3 步：查余额

```bash
python3 examples/03_check_balance.py 26
```

显示两层，币名自动识别（USDC 或 USDT，看链上声明）。若 MO=1 有结算币余额 —— 可直接下单。若钱只在 mo=0（DexLedger），要迁移到 MO=1：

```python
# 用 common.py 的一行调用
from common import send_exchange, keys
pk = keys.PrivateKey(bytes.fromhex("<你的私钥>"))
send_exchange(pk, {"type":"enrollUserToMarketOwner","marketDeployerId":1})
send_exchange(pk, {"type":"lockCollateral","marketDeployerId":1,"coinId":1,"amount":"1000000000000"})
```

## 第 4 步：看行情

```bash
python3 examples/04_market_info.py 1
```

关键看 `priceReady`：
- `true` → 合约就绪，下单能真的成交。
- `false` → 合约存在但撮合引擎不接单。下单会返 `202 accepted` 但静默丢弃。

若 `priceReady: false`，等就绪或换个合约。

## 第 5 步：下单

```bash
python3 examples/05_place_order.py 0x<你的私钥> 1 100 1 buy
```

参数：
- `0x<你的私钥>` — 你的私钥
- `1` — contractId（跑 `11_show_configs.py` 看所有合约）
- `100` — 限价
- `1` — 数量
- `buy` — 方向

返回：
```
http 202
body {"status":"accepted","response":{"type":"order","data":{"count":1}}}
```

`202 accepted` 表示 HTTP 层收下了。等 1-2 秒确认订单真的挂进 orderbook：

```bash
python3 examples/06_cancel_order.py list 26
```

看到 `status: Open` 的订单，说明成功挂上了。

如果 `userOrders` 返回 0 但 HTTP 是 202，那撮合引擎静默丢弃了。常见原因：
- `priceReady: false`（看第 4 步）
- 价格超出 price-band（跟 markPx 差太远）
- 保证金不够（看第 3 步）
- reduce-only 但没有对应仓位

## 第 6 步：撤单

```bash
python3 examples/06_cancel_order.py cancel 0x<私钥> 1 <oid>
```

或者一键撤掉某合约上所有单：
```bash
python3 examples/06_cancel_order.py cancel-all 0x<私钥> 1
```

## 然后呢

你已经跑通了完整流程。从这里可以继续：

| 我想… | 看 |
|---|---|
| 大量下单 / 写机器人 | [../skills/upside-trading/references/place-order.md](../skills/upside-trading/references/place-order.md) |
| 实时看价（不轮询） | [../skills/upside-websocket/SKILL.md](../skills/upside-websocket/SKILL.md) |
| 用单独的 key 跑机器人 | [../skills/upside-advanced/references/agent-delegation.md](../skills/upside-advanced/references/agent-delegation.md) |
| 给仓位加止盈止损 | [../skills/upside-advanced/references/tpsl.md](../skills/upside-advanced/references/tpsl.md) |
| 看懂某个报错 | [faq.zh-CN.md](faq.zh-CN.md) 或 [../skills/upside-advanced/references/error-codes.md](../skills/upside-advanced/references/error-codes.md) |
| 增加资金 | 联系 Upside 团队 |

## AI 辅助模式

如果你用 Claude Code、Cursor 或其他 AI 编码工具，上面的内容都不用读。直接跟 AI 说"我想在 Upside 上试试交易"，它会自动按 skill 流程带你完成。详见 [../README.md](../README.md#skill-loading)。

## 新手最常见的 3 个问题

完整列表见 [faq.zh-CN.md](faq.zh-CN.md)。最常见的三个：

1. **`inviteCode required`** —— 您把它放到了 `action` 里，它应位于 envelope 层。
2. **balance 字段全是 `null`** —— 您使用了 `marketOwnerId`，应使用 `marketDeployerId`。
3. **订单返 202 但查不到** —— 检查合约的 `priceReady`。

## 术语中英对照

| 中文 | 英文 |
|---|---|
| 钱包 / 地址 | wallet / address |
| 账户号 | accountId (aid) |
| 主钥 / 母钥 | master (key) |
| 代理钥 / 机器人钥 | agent (key) |
| 保证金 | collateral / margin |
| 挂单 | place order / limit order |
| 撤单 | cancel order |
| 一键撤 | cancel all |
| 行情 | market state |
| 盘口 | order book (l2Book) |
| 标记价 | mark price (markPx) |
| 指数价 | index price (indexPx) |
| 最新成交价 | last price (lastPx) |
| 资金费率 | funding rate |
| 止盈 / 止损 | TP (take profit) / SL (stop loss) |
| 条件单 | conditional order |
| 触发价 | trigger price |
| 杠杆 | leverage |

## 其他

- 完整概念图：[../README.md](../README.md)
- API 层参考：[../skills/](../skills/)
- 安全说明：[../SECURITY.md](../SECURITY.md)
- 英文版：[getting-started.md](getting-started.md)
