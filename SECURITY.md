# Security notes

## Mainnet holds real funds

The skills and examples target **Mainnet** (`https://upsidemax.xyz`) by default.
A Mainnet key controls real funds, so:

- **Keys stay local.** Scripts save generated keys to the gitignored `.env`
  (`examples/`) or `~/.upside_test.<host>.json` (`upside-test`), both readable
  only by you. They never print a private key. Back these files up yourself.
- **Never paste a private key into a chat with an AI**, an issue, or a log. If an
  AI asks you for one, refuse and generate a fresh key locally with
  `python3 examples/01_register.py`.
- **Start small.** Try a flow with the smallest order size first; prefer a
  resting limit order away from the market over a market order.
- **Use a separate key per environment.** Devnet (`https://dev.upsidemax.xyz`) is
  for testing; do not reuse a key that holds Mainnet funds there.

## What you must NOT do

1. **Never** commit private keys. `.gitignore` covers `*.pem`, `.env*`, `secrets/`, and `wallets/`.
2. **Never** accept or relay a private key over chat.
3. **Never** override `UPSIDE_CHAIN_ID` to a value that does not match the
   environment — signatures over the wrong chain ID are rejected.

## Invitation code

Registration requires an invitation code on both Mainnet and Devnet — request one from the UpsideMAX team and provide it via the `UPSIDE_INVITE_CODE` environment variable. Invite codes are single-use.

## Reporting a vulnerability

If you find something that lets any user grant themselves funds, take another user's funds, or bypass the invite gate, please file a private security advisory rather than a public issue.
