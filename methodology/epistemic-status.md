# Epistemic statuses

Every number and every conclusion published by this project carries one status.
The status is assigned **before** publication, not after a failure.

| status | meaning | what must be shown |
|---|---|---|
| `Measured` | direct observation, reproducible by a route or link | endpoint/command and the raw response |
| `Derived` | computed from measured data | the formula, in the text |
| `Inferred` | interpretation | at least one alternative explanation |
| `Proposed` | recommendation, political or product | that it is a recommendation, not a finding |
| `Unverified` | not independently reproduced | who could reproduce it |
| `Retracted` | withdrawn | why, and what replaces it |

## Four separate things, never merged in one paragraph

observation → measurement → interpretation → political proposal.

Why this rule exists: without it, a political position can be presented as a
neutral statistic — "laundering opinion through dashboards". The failure is not
hypothetical: on 2026-10-03 a ranking figure ("2nd of 23") was published as a
fact while it was an artifact of a narrow observation window. The corrected value
was "4th of 76". Record: `ledger/CORRECTIONS.md`, entry C-0001.

## Practical marking

A post or report that contains numbers starts with the header described in
`contracts/POST_HEADER.md`. A short political comment carries four lines: role,
post type, conflict, and which part is opinion.
