# Verify this repository in five minutes

Nothing here needs an account on the board, a key, or contact with the author.
Requirements: `git`, `bash`, `python3`, `coreutils`.

```bash
git clone https://github.com/konantgit-sys/truthgate.git
cd truthgate
```

## Check 1 — the bytes are the published bytes

```bash
bash scripts/verify.sh
```

What it does, in order, and what each step proves:

| step | what is compared | why it matters |
|---|---|---|
| 1 | every file against `SHA256SUMS` | the text you are reading is the text that was published; no silent edit afterwards |
| 1b | every contour file *is listed* in `SHA256SUMS` | a hole in the list would let a file ride along unhashed. `SHA256SUMS` itself is the only file allowed to be absent from its own list |
| 2 | number of ledger entries and their size | parity with the working catalogue is checked by a number, not by eye |
| 3 | method manifest root, when present | the frozen method set is rebuilt from its manifest and compared |

Expected: `ИТОГ: OK — контур сходится`, exit `0`.
On a real problem it prints the offending path and exits `1`.

The coverage check has its own regression: `bash scripts/test_sums_coverage.sh`
truncates the list and requires the verifier to block, and separately requires a
nested manifest of the same name to be treated as a contour file rather than as
"the manifest itself". A check that has never blocked a bad input is not a check.

## Check 2 — the gate actually rejects things

```bash
bash scripts/gate_selftest.sh
```

The gate is what stands between "I measured it" and "I published it". The self-test
feeds it five deliberately leaky inputs and one correct input, and requires each
leaky one to be rejected **for its own reason** — not merely rejected.

Expected: `ВЕРДИКТ: PASS — все пять дырявых отвергнуты своей причиной, верный прошёл`, exit `0`.

Reading the reasons is the interesting part: each one is a real failure mode that
occurred before the rule existed. They are listed in
[`methodology/claim-gate.md`](../methodology/claim-gate.md).

## Check 3 — a single claim, by hand

Pick any entry in [`ledger/CORRECTIONS.md`](../ledger/CORRECTIONS.md). Each entry
carries `original_claim`, `claim_type`, `issue`, `impact`, `corrected_value`,
`evidence`. The `evidence` line names the command or route that produced the
number, so the entry can be re-run rather than believed.

## Check 4 — the method set is frozen, not just described as frozen

```bash
python3 scripts/method_freeze.py --verify
```

Compares the current method files against the recorded snapshot and prints the
root hash. Expected: `OK — N файлов методик совпадают со снимком от <date>`.
An edit without a dated ledger entry turns this red and names the changed file —
which is exactly what happened to the author, and is recorded as a ledger entry.

## Check 5 — no secret reaches the public side

Every push is scanned before it is allowed out. The scanner rejects paths and
patterns, not "looks suspicious": credentials belong in environment variables
(`BOARD_KEY_FILE`), never in code or in a copied text.

If you ever find a secret here, `SECURITY.md` says what to do: open an issue titled
`SECURITY:` with the minimum needed to reproduce, and do not publish the secret.

## Exit codes

| code | meaning |
|---|---|
| `0` | everything matched |
| `1` | a real discrepancy — the output names it |
| `2` | refusal: internal material reached a text that was about to be published |

## What a pass does *not* prove

It does not prove the methods are right, the analysis is sound, or the author is
honest. It proves one narrower thing, which is the only thing a repository can
prove: **the published files are the files that were verified, and the checks that
guard them can fail.**

Claims about the world are argued in the ledger and on the board, in public, where
they can be contradicted.
