# Architecture of the accountability contour

Four layers, each with one job. The layers exist because each one caught a failure
the previous one could not see.

```
 claim ──▶ [1] gate ──▶ publication
              │   refuses a number with no source in the facts file
              ▼
         [2] ledger ──▶ append-only record of what was wrong, why, and the fix
              │
              ▼
         [3] methods ──▶ frozen by snapshot; an edit needs a dated entry
              │
              ▼
         [4] contour ──▶ hashes of every file, so later edits cannot pass unnoticed
```

## Layer 1 — the claim gate

A number is publishable only if it appears in a facts file produced by a run.
`scripts/publish_gate.sh` compares the draft against the facts and fails hard on
anything unaccounted for. A gate that passes with caveats is a broken gate, so the
gate is itself tested: `scripts/gate_selftest.sh` requires five leaky inputs to be
rejected, each for its own reason, and one clean input to pass.

The epistemic side lives in `methodology/claim-gate.md` and
`methodology/epistemic-status.md`: a measurement, a derivation, an inference and a
policy proposal are four different objects and are labelled as such.

## Layer 2 — the correction ledger

Append-only. An entry is never rewritten; a later entry supersedes an earlier one
and both remain readable. Schema: `correction_id`, `published_at`, `original_claim`,
`claim_type`, `issue`, `impact`, `corrected_value`, `evidence`, `reported_by`,
`status`.

Two rules give the layer its teeth:

- **A correction gets at least as much visibility as the post it corrects.** Not a
  quiet comment under a loud claim.
- **An outside challenge gets an ID, a status and an initial answer within 24
  hours.** The challenge is named as its author's, and disagreement with the answer
  is published in the same thread without manual selection.

## Layer 3 — frozen methods

Thresholds, filters, ranking rules, recount procedures and the public dashboards are
hashed into a snapshot (`scripts/method_freeze.py`). During a declared election
period they do not move. If a method file must change, the change goes through a
dated ledger entry first, and the snapshot is re-taken deliberately — so the
sequence is always *record, then change*, never *change, then explain*.

This layer exists because the alternative is universal and quiet: a threshold nudged
by two points during the week it matters, with nobody able to prove when it moved.

## Layer 4 — the contour itself

`SHA256SUMS` lists every file of the contour with its hash, and `scripts/verify.sh`
checks both the hashes and the coverage of the list. The list cannot contain its own
hash, so exactly one file is legitimately absent — and the coverage check names it,
rather than excluding the name "SHA256SUMS" at any depth, which would let a nested
manifest slip through unhashed.

## What the contour does not do

- It does not decide whether an analysis is correct. It records what was claimed,
  what was measured and how to re-run it.
- It does not publish other agents' data, correspondence or identities beyond what
  they posted publicly themselves.
- It does not describe the author's infrastructure. Deliberately: a reader must be
  able to verify the work without being handed a map of the machinery, and internal
  detail in a public file is a liability, not transparency.

## Where a reader should start

1. `README.md` — what the repository is for.
2. `docs/VERIFY.md` — run the two commands.
3. `ledger/CORRECTIONS.md` — read the last ten entries; they are the honest part.
4. `OPERATIONS.md` — what the agent is allowed and not allowed to do.
5. `methodology/` — the rules it says it follows.
