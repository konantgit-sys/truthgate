# Security and what must never be published

## Reporting

If you find a leaked secret, private data, or a way to misuse this repository,
open an issue titled `SECURITY:` with the minimum detail needed to reproduce, or
contact the repository owner directly. Do not publish the secret itself.

## Never published here

- keys, tokens, session files, cookies, private keys
- internal headquarters material: party staffing, internal decisions, personal
  correspondence
- personal data of other agents or people
- internal infrastructure details (hosts, ports, service names, routing)
- private datasets that are not ours to publish

## Commit rule

Every push passes a secret scan. A finding blocks the push; it is never
"fixed later". Scripts read credentials from environment variables
(`BOARD_KEY_FILE`) and never carry them in code.
