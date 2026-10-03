# Field evaluation (pair combat)

`Derived`, formula published so it can be recomputed from the raw pair table:

```
score(agent) = Σ over pairs ( 3 · wins + ties )
```

Check: with 20 fighters every fighter meets every other once, so the pair table
holds 190 rows for a complete field. A complete field with 190 rows and a partial
field with 190 rows can look identical in totals and still be different tables —
therefore the field completeness is asserted separately from the score.

## Verified numbers (2026-10-03)

- pairs in a complete 20-fighter field: **190 / 190**
- the published table and the recomputed table were compared row by row

## Refusal to compute

If the field is incomplete, no score and no place are published: the result states
`поле неполное` with the reason. Publishing a place computed on a partial field is
how a losing position is dressed as a winning one.

## Staleness

Internal consistency is not freshness. A table can be fully consistent and still
describe a state that no longer exists, so the live comparison (the `control`
block of the gate) is required in addition to the recomputation.
