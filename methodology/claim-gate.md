# Claim gate: a publication barrier that actually blocks

`scripts/publish_gate.sh <draft.md> <facts.json>` wraps `scripts/verify_claim.py`
and `scripts/truthgate/gate.sh`.

Exit codes: **0** pass, **1** blocked (claim not supported by the measured run),
**2** usage error. A pass writes a receipt into a pass directory, and the
publisher accepts a draft only with a fresh receipt: a barrier that can be
bypassed by hand is not a barrier.

## What the facts file must contain

| field | why |
|---|---|
| `numbers` | the closed list of values produced by the run. Any number in the text that is not in this list is a hard FAIL, not a warning. |
| `denominator` | what the shares are counted from; without it a percentage is meaningless |
| `control` | a **live** check (`url` + `path` + `expect`): a claim that only agrees with itself is not verified. The word "checked" is not a check. |
| `alternative` | the competing explanation and what would disprove the conclusion |
| `window` | the time window the measurement belongs to |
| `source` | where the numbers came from |

## Template rendering

If `tpl/<name>.tpl.md` exists for the draft, the gate re-renders the text from the
same facts and requires a byte-identical match. A number edited by hand in the
draft then differs from the render, and publication is blocked. This closes the
hole found on 2026-09-23: a substituted number passed because the wrong value
happened to be present in the facts list as a date token.

## The self-test is the proof

`scripts/gate_selftest.sh` feeds **five leaky inputs**, each of which must be
rejected **for its own reason**, plus one correct input that must pass:

| input | expected reason |
|---|---|
| `good` | code 0 — correct input passes |
| `leak` | number outside the run |
| `noden` | no denominator |
| `nolive` | control not executable (declared by a word) |
| `noalt` | no alternative explanation |
| `stale` | live control disagrees (locally consistent, globally outdated) |

Real result of a clean staging run on 2026-10-03: `ВЕРДИКТ: PASS`, exit 0 —
six of six inputs behaved as expected, and the ballot-id rule test passed 17
checks. A test that has never blocked a bad input is not a test.

The fifth input is the important one: it cannot be caught by any internal
consistency check, because everything is locally consistent and only the live
value has moved on.
