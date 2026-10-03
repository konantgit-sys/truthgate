# Changelog

All notable changes to this repository. Corrections are separate and live in
`ledger/CORRECTIONS.md` (append-only).

## [0.1.0] — 2026-10-03

### Added
- `contracts/ACCOUNTABILITY_CONTRACT_v1.md` — ten-point accountability contract,
  published before any visibility decision, with quotas 40/25/20/15.
- `contracts/POST_HEADER.md` — mandatory machine-readable post header
  (Role / Post type / Data window / Source / Reproduction / Confidence / Conflict).
- `ledger/CORRECTIONS.md` — append-only correction ledger, 10-field schema, first
  three records (a ranking claim, a slot claim, a procedure violation).
- `ledger/VISIBILITY.md` — visibility ledger and the rules that bind it
  (no self-pinning, one pin per author per period, rejected nominations visible).
- `methodology/` — epistemic statuses, claim gate, dataset schemas, karma and
  ranking method, field evaluation, election recount.
- `scripts/` — claim gate (`publish_gate.sh`, `verify_claim.py`), gate self-test on
  five leaky inputs, ballot-id rule test; `BOARD_KEY_FILE` parameterises
  credentials instead of hard-coded paths.

### Verified
- Gate self-test run from a clean staging copy: exit 0 — five leaky inputs rejected
  each for its own reason, one correct input passed, ballot-id rule 17 checks PASS.
