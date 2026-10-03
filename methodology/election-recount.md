# Election recount (IRV-2)

`Derived`. The contract's counting rules are re-implemented independently and the
result is compared with the published rounds field by field: counts, eliminated
candidate, exhausted ballots, reason for elimination.

## Rules as implemented

1. Each round, votes are counted over non-exhausted ballots.
2. A candidate wins with a majority of non-exhausted ballots:
   `top · 2 > non_exhausted`.
3. Otherwise the lowest candidate is eliminated and their votes transfer.
4. Ballots that cannot transfer (no remaining preference) are marked
   `exhausted` and are removed from the base of the following rounds.
5. A round below the support floor adds a removal step rather than ending the
   count — this is where an earlier naive implementation stopped one round early:
   it stopped on round 6 while the official count removed a candidate in round 6
   and continued, so the transfer to round 7 changed the winner.

## Comparison method

For each published round: `counts`, `eliminated`, `exhausted`, `reason`. A
discrepancy in any field is reported as a discrepancy, not averaged away. A
matching total with a different round-by-round path is still a mismatch and is
reported as such.

## What a recount does not prove

Agreement with the published result does not prove the outcome was correct: both
counts can share the same wrong assumption. It proves only that the arithmetic and
the rule application were reproduced independently. Interpretation belongs in
`Inferred`, not here.
