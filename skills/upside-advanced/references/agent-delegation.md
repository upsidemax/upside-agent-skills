# Agent Delegation

Approve a "bot" address that can trade under the master account without holding funds directly. Master keeps withdrawal and account-management authority; agent gets TRADE-only.

## Workflow

### Grant an agent

1. **Master must be registered and funded** (see [`../../upside-onboarding/SKILL.md`](../../upside-onboarding/SKILL.md)).
2. **Choose slot**:
   - Anonymous slot: omit `agentName`. Only ONE anon slot per master.
   - Named slot: pass `agentName: "<label>"`. Up to 3 named slots.
3. **Show Confirming Response**. See [Confirming Response](#confirming-response). Do NOT skip.
4. **Run**:
   ```bash
   python3 examples/08_agent_delegation.py <master_priv> <agent_priv> [agentName] [validUntil_ms]
   ```
5. **Verify** via `userAgents` (see [List active agents](#list-active-agents)).
6. **Render the Agent Granted template**.

### Revoke an agent

1. **List current agents** first via `userAgents` to confirm the target.
2. **Show Confirming Response** — revoke is irreversible.
3. **Run**:
   ```json
   {"type":"revokeAgent","agentAddress":"0xagent…"}
   ```
4. **Verify** the agent is gone from `userAgents`.
5. **Render the Agent Revoked template**.

### List active agents

```json
{"type": "userAgents", "accountId": "5"}
```
Response:
```json
{
  "type": "userAgents",
  "accountId": "5",
  "agents": [
    {"address":"0xa…", "name":"my-bot", "validUntil":"0", "isNamed":true},
    {"address":"0xb…", "name":"",       "validUntil":"1784600000000", "isNamed":false}
  ]
}
```

## Model

- **Master**: full authority (TRADE + FUND + GOV). Signs `approveAgent`, `revokeAgent`, `withdraw`, `lockCollateral`, etc.
- **Agent**: TRADE authority only. Signs `order`, `cancel`, `modify`, `cancelAll`, `tpSl`, `cancelTpSl`, `updateLeverage`, `cancelByCloid`.

Backend recovers signer, sees it's a registered agent for some master, routes the action under that master's account.

## Slot limits

- 1 anonymous slot (`agentName` empty or omitted)
- 3 named slots (each with a distinct `agentName`)

Approving a new agent to an existing named slot **overwrites** — old agent unbound, new agent takes over.

Approving a 4th distinct named agent → `errorCode: 28 "named agent quota (3) exceeded"`.

## approveAgent — action

```json
{
  "type": "approveAgent",
  "agentAddress": "0xagent…lowercase…",
  "agentName": "my-bot",              // optional; omit for anon slot
  "validUntil": 1784600000000         // optional; 0 or omitted = permanent
}
```
Signed by **master**.

## validUntil semantics

| value | behavior |
|---|---|
| omitted | permanent (never expires) |
| `0` | permanent (same as omit) |
| past timestamp (ms) | rejected at `approveAgent` time: `errorCode: 1, "invalid validUntil (must be 0 or > blo…)"` |
| future timestamp | works until `now >= validUntil`; agent signs get rejected as "no registered account" after |

Once past `validUntil`, master must re-approve (with new `validUntil`) to renew. Backend does not auto-renew.

## revokeAgent — action

```json
{"type": "revokeAgent", "agentAddress": "0xagent…"}
```
Signed by **master**.

Response:
- Success: `{"agentAddress":"0x…"}`
- `errorCode: 29 "agent not found for this account"` — agent isn't currently under this master (already revoked, or belongs to another master).

## Permission matrix

| action | agent can sign? | notes |
|---|:---:|---|
| `order` | ✅ | routes under master |
| `cancel`, `cancelByCloid`, `cancelAll` | ✅ | |
| `modify` | ✅ | |
| `tpSl`, `cancelTpSl` | ✅ | |
| `updateLeverage` | ✅ | |
| `lockCollateral`, `unlockCollateral` | ❌ | `errorCode: 30` "agent may sign trade actions only" |
| `withdraw`, `transfer` | ❌ | `errorCode: 30` (or `http 400 unknown action.type` on QA — not yet implemented) |
| `approveAgent`, `revokeAgent` | ❌ | `errorCode: 30` — agents can't manage other agents |
| `registerAccount` | ❌ | signer mismatch (agent addr != action.address) |

## Templates

### Confirming Response — grant

```
⚠  About to GRANT trading authority on Upside (QA).

  Master:       {master_aid} — {master_addr}
  Agent addr:   {agent_addr}
  Slot:         {"anonymous" | "named: " + agent_name}
  ValidUntil:   {"permanent (never expires)" | "<UTC ISO>"}

  Once granted, the agent's private key can place, modify, and cancel orders
  under the master account. It CANNOT deposit or withdraw.

Reply "yes" to proceed, anything else to cancel.
```

### Agent Granted

```
✓ Agent approved on Upside (QA)

  Master:      {master_aid}
  Agent:       {agent_addr}
  Slot:        {anonymous | named: <name>}
  ValidUntil:  {permanent | UTC ISO}

  Total agents now under this master: {n} (anon: {n_anon}, named: {n_named} of 3)

  Revoke:  python3 examples/…  (revokeAgent action, signed by master)
```

### Confirming Response — revoke

```
⚠  About to REVOKE agent on Upside (QA).

  Master:       {master_aid} — {master_addr}
  Agent addr:   {agent_addr}
  Slot:         {anon | named: <name>}
  Was valid:    until {validUntil}

  This is irreversible. Any pending orders placed by the agent will remain,
  but the agent's key can no longer place new orders.

Reply "yes" to proceed, anything else to cancel.
```

### Agent Revoked

```
✓ Agent revoked on Upside (QA)

  Master:  {master_aid}
  Agent:   {agent_addr}
```

## Confirming Response

- `approveAgent`: **always confirm** — grants trading authority.
- `revokeAgent`: **always confirm** — irreversible removal.
- `userAgents` (list): **skip** — read-only.

## Common failure modes

| code | message | cause | fix |
|---:|---|---|---|
| 1 | `invalid validUntil (must be 0 or > blo…)` | past timestamp | pass a future ms-timestamp or `0` |
| 27 | `agent address bound to another master` | trying to approve an already-bound agent | revoke first from other master, or use a different agent |
| 28 | `named agent quota (3) exceeded` | 4th distinct named agent | revoke one, or reuse an existing name (overwrites) |
| 29 | `agent not found for this account` | revoke targeting non-existent binding | verify with `userAgents` first |
| 30 | `agent may sign trade actions only` | agent tried FUND or GOV action | sign with master's key |
| — | `signer 0x… has no registered account` (400) | agent's `validUntil` passed, OR agent revoked, OR never approved | re-approve, or master signs |

## See also

- [tpsl](tpsl.md) — agents can manage TP/SL
- [error-codes](error-codes.md) — full errorCode table
- [`../../upside-onboarding/_shared/signing.md`](../../upside-onboarding/_shared/signing.md) — signature recovery details
- [_shared/confirming-response.md](../../upside-onboarding/_shared/confirming-response.md) — the safety gate
