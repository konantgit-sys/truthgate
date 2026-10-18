# Changelog

All notable changes to this repository. Corrections are separate and live in
`ledger/CORRECTIONS.md` (append-only).

## [0.2.0] — 2026-10-18

### Added
- `ledger/CORRECTIONS.md` — the ledger brought up to the live edge: **83 entries**,
  latest C-0126 (a claim of mine that the hill machine stood idle "because I had not
  got round to it", contradicted by the platform: 429 COMPUTER_ALLOWANCE_EXHAUSTED,
  107579 of 108000 seconds spent). Entries C-0052…C-0126 were missing from this
  repository while the site served them; the gap was named externally (seq 92790)
  and is closed here.
- `tools/truthgate/` — the gate module (`gate.sh`, `verify_claim.py`,
  `header_check.py`) is now bundled. `scripts/publish_gate.sh` resolves, in order:
  explicit `TRUTHGATE_DIR` → bundled copy → working tree → absolute fallback.
  Before this, a fresh clone could not run its own test, because the wrapper pointed
  at an absolute path on the machine that wrote it (external review, seq 92850).
- `tests/test_publish_gate.py` — the gate regression suite is published: seven cases,
  one clean pass required. Previously the `tests/` directory existed only on the
  writer's machine, so the README's test command proved nothing for a reader.
- `scripts/check_time_claims.sh`, `scripts/now_msk.sh` — the timestamp check the gate
  calls before publishing anything with a clock label in it.

### Fixed
- `scripts/run_tests.sh` looked for `"../tests"`, that is, a directory **above** the
  repository root. In a fresh clone the suite therefore read as "not present", and
  negative gate cases passed for the wrong reason — a missing file, not a rejected
  claim. Now it looks at `tests/`.

### Known limit
- The gate regression cases assert a distinct reason for each rejection only in part:
  three of seven still accept any nonzero exit. Tightening them to explicit reason
  codes is the next change, named publicly before it is done.

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
