# Changelog

All notable changes to this repository. Corrections are separate and live in
`ledger/CORRECTIONS.md` (append-only).

## [0.3.1] — 2026-10-21

### Added
- `ledger/CORRECTIONS.md` — records `C-0147` … `C-0153` appended in chronological
  position: the denominator stated in `C-0147` (14 of 16, 88%), the withdrawal of
  the "word-order invariance" claim after the null model, the translation language
  check that existed for English only, dashboard and showcase edits recorded
  against `METHOD_FREEZE`, the full paths of edits that had drifted from the
  snapshot, and the freeze guard that blocked every commit after midnight.
  Nothing removed, nothing rewritten.
- The owner's name no longer appears anywhere in the public ledger: two lines of
  `C-0142` carried it, the rewriter now maps every case form to "account owner".

### Changed
- `scripts/verify_claim.py` rebuilt from the reference by `sync_gate_copies.py` —
  the public barrier must not be weaker than the working one.
- `SHA256SUMS` rebuilt from actual bytes.

### Verification
- `bash scripts/verify.sh` — verdict printed below in the same commit.

## [0.2.2] — известный остаток (принят владельцем 2026-10-18, см. `ledger/CORRECTIONS.md` C-0134)

Не скрытый дефект и не «закрыто»: остаток, который сознательно оставлен.

- В истории репозитория был коммит, в котором реестр выложен без обезличивания
  (имя владельца и внутренние пути узла). Коммит выведен из `main` перезаписью
  истории; публичная копия реестра собрана штатным публикатором и проверена —
  имён и внутренних путей нет.
- Остаток: на стороне хостинга объект этого коммита продолжает отдаваться по
  прямому адресу, если известен его идентификатор. Идентификатор удалён из всех
  наших файлов и публикаций, поэтому из репозитория и реестра его взять неоткуда.
- Полное удаление возможно только пересозданием репозитория (уничтожает историю
  и тег). Владелец это отклонил осознанно. Условие пересмотра: появление
  идентификатора в любой внешней публикации — тогда вопрос ставится заново.

## [0.2.2] — 2026-10-18

### Added
- `tools/truthgate/reasons.py` — единый словарь кодов отказа (14 причин, коды 10–23)
  и разбор по порядку проверок, а не по «важности».
- `tools/truthgate/tests/test_gate.py` — фикстуры «верный вход» получили шапку:
  до этого три положительных кейса падали на header_check и краснели не по той
  причине, которую называли.

### Changed
- `verify_claim.py` возвращает код причины, а не 1; `gate.sh` различает 10/11/12/17;
  бордовая обёртка — 18/19/22.
- `tests/test_publish_gate.py` — 12 кейсов, каждый требует свой код (было 7,
  три из них принимали любой ненулевой).
- `scripts/gate_selftest.sh` — живая версия контракта вместо прибитой 1.17.3
  и свой код на каждый из шести входов (было «ожидался 1»).
- `scripts/sync_gate_copies.py` — сверка блока docstring по образцу, а не по
  точной строке (эталон менялся, скрипт молча не синхронизировал); реальный
  путь ключа вычищается, остаток ловится проверкой; рядом с производной копией
  кладётся `reasons.py`, иначе импорт падал и код откатывался на 1.
- `reason_codes_audit.py` — код читается целиком (`\d+`, было `\d`: 16 читалось
  как 1), таблица пар обновлена на фактические коды.

### Verified
- `tests/test_publish_gate.py` — 12/12, exit 0;
- `tools/truthgate/tests/test_gate.py` — 21/21, дырявых заблокировано 10/10;
- `scripts/gate_selftest.sh` — 6/6 (5 дырявых своей причиной + верный прошёл);
- `reason_codes_audit.py` — «полное покрытие», кодов без входа 0.

## [0.2.1] — 2026-10-18

### Changed
- `ledger/CORRECTIONS.md` — updated from 83 to **86 entries**, latest C-0129. C-0127
  records the failed publication attempt (403: owner-level `permissions.push` was
  read as token-level rights — the second occurrence of that mistake), C-0128 records
  that the public copy of the ledger served C-0114 while the ledger itself had reached
  C-0127, C-0129 records the publication itself with the commit hash and the live
  checks that confirm it.

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
