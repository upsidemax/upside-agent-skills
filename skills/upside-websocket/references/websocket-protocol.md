# WebSocket Protocol

WebSocket wire format. The Upside WebSocket uses a JSON subscribe protocol: the client sends `{"method":"subscribe","subscription":{"type":"<channel>", …}}`; the server replies on `channel: "subscriptionResponse"` and then pushes updates on `channel: "<name>"`. The `{msg:"Subscribe", channels:[…]}` form is not supported and returns no data.

## Workflow

1. **Connect** to `wss://dev.upsidemax.xyz/ws`.
2. **Send subscribe** using the current format (see [Subscribe frame](#subscribe-frame)).
3. **Expect ACK** on `channel: "subscriptionResponse"` within ~500 ms.
4. **Read data** on `channel: "<type>"`.
5. On disconnect: reconnect and resend all subscriptions.

## Endpoint

```
wss://dev.upsidemax.xyz/ws
```

The connection is unauthenticated. Any client can subscribe to any channel, including `orderUpdates.<any-address>`; personal channels are effectively public.

## Subscribe frame

Client → server:
```json
{
  "method": "subscribe",
  "subscription": {"type": "<channel>", …extra params…}
}
```

Server → client (ACK):
```json
{
  "channel": "subscriptionResponse",
  "data": {
    "method": "subscribe",
    "subscription": {"type": "<channel>", …echoed params…}
  }
}
```

Then subsequent data flows on `channel: "<type>"`.

## Frame format reference

The following forms are not supported and return no data. Use the current format instead:

| aspect | not supported | current |
|---|---|---|
| envelope key | `msg` | `method` |
| subscribe value | `"Subscribe"` (uppercase) | `"subscribe"` (lowercase) |
| channel list field | `channels: ["config", "l2Book.1"]` | `subscription: {type:"l2Book", asset:"1"}` |
| channel-with-arg | dot notation: `"l2Book.1"` | structured: `{type:"l2Book", asset:"1"}` |
| ACK channel | `msg: "Subscribed"` | `channel: "subscriptionResponse"` |
| error channel | — | `channel: "error"` |

## Unsubscribe

```json
{"method": "unsubscribe", "subscription": {"type":"l2Book", "asset":"1"}}
```

## Error responses

Wrong param name:
```json
{"channel":"error", "data":{"code":"BAD_SUBSCRIPTION", "message":"missing/invalid params for type=l2Book"}}
```

Unknown channel type:
```json
{"channel":"error", "data":{"code":"BAD_SUBSCRIPTION", "message":"unknown subscription type: allMids"}}
```

## Ping / keepalive

The server does not send heartbeats. The client MUST:

- Send WS-level `ping` frames every ~30 s.
- Detect close events and reconnect.
- On reconnect, resend all subscriptions.

Example Python (using `websocket-client`):
```python
import threading, time

def ping_forever(ws):
    while ws.connected:
        try:
            ws.ping()
        except Exception:
            break
        time.sleep(30)

threading.Thread(target=ping_forever, args=(ws,), daemon=True).start()
```

## Backpressure

If the client reads slower than the server sends:

- The server buffers up to an internal limit.
- Beyond the limit, the server drops messages or closes the connection.

Design:
- Never `print()` inside the message loop on high-throughput channels.
- Move parsing to a separate thread; the read loop should only enqueue.
- For `l2Book`, use `bookVersion` to detect gaps after reconnect.

## Template — Subscribe result

Success:
```
✓ Subscribed to {channel} (asset={asset|-})
  Waiting for data. Press Ctrl+C to stop.
```

Error:
```
✗ Subscribe failed:  {error.code}  {error.message}
  Fix:                {specific suggestion, e.g. "use `asset` not `coin`"}
```

## Confirming Response

Read-only. **Skip** the Confirming gate.

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| WS handshake OK, subscribe sent, no messages | client using the unsupported `msg:"Subscribe"` form | switch to `method:"subscribe"` |
| `BAD_SUBSCRIPTION missing/invalid params for type=l2Book` | wrong param name (`coin` / `contractId`) | use `asset` |
| WS handshake returns HTTP 200 + text/html | the `/ws` path is not being proxied | verify the endpoint URL `wss://dev.upsidemax.xyz/ws`; see [`../../upside-onboarding/_shared/endpoints.md`](../../upside-onboarding/_shared/endpoints.md) |
| Connection drops after 60 s idle | no client-side ping | add a periodic ping loop |
| Messages stop after a high-volume burst | backpressure — the server closed the connection | reconnect and resume; check consumer speed |

## See also

- [channels](channels.md) — per-channel parameter matrix
- [payload-samples](payload-samples.md) — sample messages captured from QA
- [`../../upside-onboarding/_shared/endpoints.md`](../../upside-onboarding/_shared/endpoints.md) — endpoint URLs
