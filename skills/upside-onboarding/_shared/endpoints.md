# Endpoints

## Mainnet (default)

```
REST:  https://upsidemax.xyz/exchange
REST:  https://upsidemax.xyz/info
WS:    wss://upsidemax.xyz/ws
EIP-712 chainId: 9788
```

## Devnet

```
REST:  https://dev.upsidemax.xyz/exchange
REST:  https://dev.upsidemax.xyz/info
WS:    wss://dev.upsidemax.xyz/ws
EIP-712 chainId: 9767
```

Select Devnet with `UPSIDE_BASE_URL=https://dev.upsidemax.xyz`; the WebSocket URL and
chainId follow it. Mainnet holds real funds. `/exchange` handles all signed writes; `/info` handles all reads; `/ws` handles the JSON subscribe WebSocket protocol.

## Header conventions

Every request should send:

```
Content-Type: application/json
Connection: close
```

`Connection: close` is important on some Python clients — with the default `keep-alive`, some load-balancer nodes may truncate the response mid-stream.

## Reachability check

```bash
curl -s -m 5 -X POST https://upsidemax.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"marketState","asset":"1"}'
```

Expected: JSON with `type: "marketState"`. If you get an HTML page, the request did not reach the API — check the URL and method (`POST`), retry shortly, and contact the UpsideMAX team if it persists.
