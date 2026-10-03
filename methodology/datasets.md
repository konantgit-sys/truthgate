# Dataset schemas and versioning

## Versioning

Every snapshot is a **new version**, never a rewrite:

```
<dataset>-<YYYY-MM-DD>.v<n>        e.g. board-field-2026-10-03.v1
```

A manifest (`manifests/`) records, for each version:

| field | purpose |
|---|---|
| `collected_at_utc` | the instant the state existed — answers "what was known at time t" |
| `source.endpoint`, `auth`, `pages_fetched`, `cursor_final`, `sort_order`, `page_size` | so a re-run traverses the same way |
| `counts.records_total`, `records_after_dedup`, `duplicates_removed` | so deduplication is visible, not assumed |
| `normalisation` | what was changed on the way in |
| `known_gaps` | missed pages, rate-limit events, retries |
| `artefact.sha256`, `bytes` | the hash of the exact file |
| `reproduction` | a command that needs no credentials |

## Rules

1. Late data does not retroactively fix an earlier snapshot: a later fetch is a
   later version. Otherwise a late sample silently becomes an old forecast.
2. A rate-limit event is recorded, not hidden; the affected range is re-fetched
   and the gap is named.
3. Deduplication is declared. `records_total - duplicates_removed` must equal the
   published count, and the arithmetic is checkable by hand.
4. Missing is not zero. "Not measured" is written as such and never rendered as 0.

## Known gaps in current versions

- Board snapshots cover public endpoints only; private views are not included.
- Ranking depends on a live karma endpoint; when it does not answer, the place is
  reported as "not measured after retry" rather than as a lower number.
