# Endpoints

## QA

```
REST:  https://dev.upsidemax.xyz/exchange
REST:  https://dev.upsidemax.xyz/info
WS:    wss://dev.upsidemax.xyz/ws
```

TLS-terminated by nginx. `/exchange` handles all signed writes; `/info` handles all reads; `/ws` handles the JSON subscribe WebSocket protocol.

## Header conventions

Every request should send:

```
Content-Type: application/json
Connection: close
```

`Connection: close` is important on some Python clients — with the default `keep-alive`, some load-balancer nodes may truncate the response mid-stream.

## Reachability check

```bash
curl -s -m 5 -X POST https://dev.upsidemax.xyz/info \
  -H 'Content-Type: application/json' \
  -d '{"type":"marketState","asset":"1"}'
```

Expected: JSON with `type: "marketState"`. If you get an HTML page, you hit nginx SPA fallback — usually because the domain's config is missing a `location /info` proxy.
