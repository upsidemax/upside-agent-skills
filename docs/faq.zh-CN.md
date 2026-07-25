# FAQ / 常见问题（中文）

本页汇总常见错误及其解决方法。如未列出您的问题，请查阅页面底部按模块链接的参考文档。

英文版：[faq.md](faq.md)。

## 安装 / 环境

### `ModuleNotFoundError: No module named 'eth_keys'`
运行 `./install.sh` 或 `pip install eth-keys eth-utils requests websocket-client eth-hash[pycryptodome]`。

### `pip install --user ... permission denied`
在 Docker / CI 里权限受限。用 venv：
```bash
python3 -m venv .venv
source .venv/bin/activate
./install.sh
```

### `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+`
macOS 上 Python 用 LibreSSL 触发的警告，无害，忽略即可。如果实在不想看：`pip install urllib3==1.26.18` 装老版本。

### `install.sh: /bin/bash: bad interpreter`
Windows 上用 Git Bash 或 WSL。或者手动执行 pip 命令。

## 网络连接

### 请求 `https://dev.upsidemax.xyz/info` 超时
QA 环境可能暂时不可用，或您的网络阻断了该请求。
1. 运行 `curl -v https://dev.upsidemax.xyz/info` 查看具体错误。
2. 请稍后重试；若问题持续，请联系 Upside 团队。

### `POST /info` 返回 HTML 而非 JSON
该端点当前未代理 `/info`。请稍后重试；若问题持续，请联系 Upside 团队。

### WebSocket 能连上但没消息
您使用的订阅格式不受支持。服务端采用基于 JSON 的订阅协议，使用 `{"method":"subscribe","subscription":{...}}` 帧。请改为：
```json
✗ {"msg":"Subscribe", "channels":["l2Book.1"]}
✓ {"method":"subscribe", "subscription":{"type":"l2Book", "asset":"1"}}
```
详见 [../skills/upside-websocket/references/websocket-protocol.md](../skills/upside-websocket/references/websocket-protocol.md)。

## 注册

### `http 400 "inviteCode required"`
您把 `inviteCode` 放到了 `action` 里。它属于 envelope 层字段：
```json
✗ {"action":{"type":"registerAccount","address":"0x…","inviteCode":"<invite-code>"}, …}
✓ {"action":{"type":"registerAccount","address":"0x…"}, "inviteCode":"<invite-code>", …}
```
请向 Upside 团队申请邀请码，并通过 `UPSIDE_INVITE_CODE` 环境变量设置。

### `http 409 ACCOUNT_ALREADY_EXISTS`
不是错误 —— 已经注册过了。从 message 里解析 `accountId`：
```python
aid = msg.split("accountId=")[-1].strip()
```
然后正常继续。

### `http 401 "recovered address … does not match action.address"`
签名的私钥与 `action.address` 不对应。服务端要求 signer == address；不能替他人注册。请用正确的私钥重新签名。

## 资金

### `depositNonce = 0`，60 秒后仍无资金
QA 空投偶尔不会到账。最简单的补救办法是重新注册一个新钱包：
```bash
python3 examples/01_register.py
```
空投未到账通常仅针对单次注册，新的注册一般会成功。

### 余额字段全是 `null`
您使用了 `marketOwnerId` 而非 `marketDeployerId`。正确的字段是 `marketDeployerId`；使用 `marketOwnerId` 会返回 null 字段而非报错。
```json
✗ {"type":"userAccount","accountId":"5","marketOwnerId":1}
✓ {"type":"userAccount","accountId":"5","marketDeployerId":1}
```

### 钱在 `chainBalances` (mo=0) 但 `crossCollaterals` (MO=1) 空
空投落到了 DexLedger 层。要下单需要迁移到 MO=1：
```python
send_exchange(pk, {"type":"enrollUserToMarketOwner","marketDeployerId":1})
send_exchange(pk, {"type":"lockCollateral","marketDeployerId":1,"coinId":1,"amount":"1000000000000"})
```

## 交易

### 下单返 `http 202` 但 `userOrders` 里查不到
撮合引擎静默丢弃。常见原因：

| 原因 | 检查方式 |
|---|---|
| `priceReady: false` | `python3 examples/04_market_info.py <contractId>` |
| 价格超出 price-band | 对比 `p` 和 `markPx * (1 ± priceBandBps/10000)` |
| `marginAvailableForOrder` 不够 | `python3 examples/03_check_balance.py <aid>` |
| reduce-only 但没匹配的仓位 | 查 `userAccount.positions` |
| 合约被暂停或下架 | 换个合约试 |

### `errorCode: 30 "agent may sign trade actions only"`
签名者是 agent，但操作是 FUND（存取款）或 GOV（授权注册）类。用 master 私钥签。

如果是 TRADE 类操作（比如 `order`）出这错，说明你的 agent 绑定失效或过期了。查 `userAgents`。

### `errorCode: 27 "agent address bound to another master"`
这个 agent 地址已经被别的 master 授权过。换个 agent 地址，或者先让原来的 master revoke。

### `errorCode: 28 "named agent quota (3) exceeded"`
已经有 3 个具名 agent。revoke 一个，或者用现有名字（会覆盖对应槽位）。

### `errorCode: 4 "unknown contract"`
`a` 指向的 contractId 不存在。用 `marketState` 确认：
```python
info({"type":"marketState","asset":"1"})  # asset 是字符串
```

### `errorCode: 31 "nonce already used"`
重放攻击 —— 同一 envelope 发了两次。用新 nonce 重生成。

### `errorCode: 31 "nonce too far in the future"`
nonce 比当前时间超前 > 24h。用 `int(time.time() * 1000)`。

### `errorCode: 1 "invalid validUntil (must be 0 or > blo…"`
`validUntil` 传了过去的时间戳。用 `0` 表示永久，或者一个未来的时间戳。

## WebSocket

### `{"channel":"error","data":{"code":"BAD_SUBSCRIPTION","message":"missing/invalid params for type=l2Book"}}`
参数名错。用 `asset`（字符串形式的 contractId）：
```json
✗ {"type":"l2Book","coin":"1"}
✗ {"type":"l2Book","contractId":1}
✓ {"type":"l2Book","asset":"1"}
```

### WS 连接空闲 60 秒后断开
Server 不发心跳。客户端 30 秒一次主动 ping：
```python
import threading, time
def ping_forever(ws):
    while ws.connected:
        try: ws.ping()
        except Exception: break
        time.sleep(30)
threading.Thread(target=ping_forever, args=(ws,), daemon=True).start()
```

### WS 返回 "unknown subscription type: allMids"
该订阅类型当前不受支持。请改用按合约订阅的 `l2Book`。

## 签名

### `http 401 SIGNATURE_INVALID` 但我确定私钥没错
常见原因：
1. `v` 字节错（必须是 27 或 28，不是 0/1）
2. Typed action 在 wire JSON 里漏了可选字段（`agentName` / `validUntil` / `amount` / …）。服务端对缺失字段的默认处理与客户端不同，字段必须显式出现在 JSON 中。`examples/common.py` 的 `sign_envelope` 会自动填入默认值；若您自行实现签名，请复制 `_TYPED_DEFAULTS` 步骤。
3. Agent path 的 canonical JSON 有空格或 key 顺序不对（必须 `sort_keys=True, separators=(",",":")`）
4. Nonce 不一致（envelope 层 nonce 跟传给 digest 的 nonce 不同）
5. EIP-712 domain 错了（name/version/chainId 要跟 server 一致：`{Exchange, 1, 9767}`）

请以 `examples/common.py` 中的 `sign_envelope` 作为参考实现。

### Envelope 层 vs action 层字段
- `action`：包含 `type` 和 action 特有字段
- Envelope 层（跟 `action` 平级）：`signature`、`nonce`、`inviteCode`（仅 registerAccount 用）

**不要**把 `nonce` 或 `inviteCode` 放进 `action`。**不要**把 `type` 放到 envelope 层。

## 环境 / 配置

### 怎么切换到别的环境（UAT / mainnet）？
在 `.env` 里设 `UPSIDE_BASE_URL`（或 export 环境变量）。`examples/common.py` 自动读取。**不要**指向 mainnet —— 这些脚本生成的私钥都是一次性 QA-only 的。

### 私钥怎么跨脚本运行复用？
把 `.env.example` 拷贝为 `.env`，填 `USER_PRIVATE_KEY`。`common.py` 用 `load_user_wallet()` helper 自动读取。见 [.env.example](../.env.example)。

### 能用 TypeScript / Rust / Go 代替 Python 吗？
可以。移植 `examples/common.py` 里的签名 + HTTP 封装即可。wire format 与语言无关，签名算法详见 [../skills/upside-onboarding/_shared/signing.md](../skills/upside-onboarding/_shared/signing.md)。

## 更多

- 完整错误码表：[../skills/upside-advanced/references/error-codes.md](../skills/upside-advanced/references/error-codes.md)
- 概念入门：[getting-started.zh-CN.md](getting-started.zh-CN.md)
- Skill 索引：[../skills/README.md](../skills/README.md)
- 如果 AI 助手出现困惑，可直接让它阅读 `skills/*/SKILL.md` —— 这些文件供 AI 助手从头到尾阅读。
