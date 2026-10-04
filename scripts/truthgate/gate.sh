#!/bin/bash
# Универсальный шлюз перед ЛЮБОЙ публикацией вывода с цифрами.
# Общий модуль — вызывается из борды, отчётов, документов и любых проектов.
#
#   gate.sh <draft.md> <facts.json>
#
# exit 0 — PASS (числа сверены с прогоном), публиковать можно
# exit 1 — FAIL: нет знаменателя / контроля / альтернативы, либо в тексте
#          есть числа, которых нет в facts.numbers (значит взяты не из замера)
# exit 2 — ошибка вызова (нет черновика, не указаны аргументы)
#
# Метка пропуска кладётся в TRUTHGATE_PASS_DIR (по умолчанию ~/.truthgate/pass).
# Бордовая обёртка задаёт свой каталог, чтобы reply.py видел ту же метку.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DRAFT="${1:-}"; FACTS="${2:-}"
if [ -z "$DRAFT" ] || [ -z "$FACTS" ]; then
  echo "ИСПОЛЬЗОВАНИЕ: gate.sh <draft.md> <facts.json>"; exit 2
fi
[ -f "$DRAFT" ] || { echo "✗ нет черновика: $DRAFT"; exit 2; }
[ -f "$FACTS" ] || { echo "✗ НЕТ FACTS: без прогона цифры публиковать нельзя ($FACTS)"; exit 1; }

# ── ДОПОЛНИТЕЛЬНЫЙ БАРЬЕР (04.10.2026): шапка Role/Post type/Data status/Conflict
# и метка unreplicated для кампанийных цифр. До этого правило жило в документах
# и проверялось только вниманием: шлюз не проверял ни одного поля шапки.
if ! python3 "$HERE/header_check.py" "$DRAFT"; then
  echo "ШЛЮЗ: CLOSED — публикация заблокирована (шапка/метки, см. причины выше)"
  exit 1
fi

python3 "$HERE/verify_claim.py" --facts "$FACTS" --draft "$DRAFT"
code=$?
if [ $code -eq 0 ]; then
  echo "ШЛЮЗ: OPEN — вывод прошёл сверку с прогоном"
  # Метка пропуска: потребитель принимает файл только со свежим PASS.
  # Барьер, который можно обойти вручную, барьером не является.
  PASS_DIR="${TRUTHGATE_PASS_DIR:-$HOME/.truthgate/pass}"
  mkdir -p "$PASS_DIR"
  python3 - "$DRAFT" "$FACTS" "$PASS_DIR" <<'PYEOF'
import hashlib, json, os, sys, time
draft, facts, outdir = sys.argv[1], sys.argv[2], sys.argv[3]
h = hashlib.sha256(open(draft,'rb').read()).hexdigest()
rec = {"draft": os.path.basename(draft), "draft_sha16": h[:16], "facts": os.path.basename(facts),
       "gate_at": int(time.time()), "exit": 0}
json.dump(rec, open(os.path.join(outdir, h[:16] + ".json"), 'w'), ensure_ascii=False)
print("метка пропуска: %s.json" % h[:16])
PYEOF
else echo "ШЛЮЗ: CLOSED — публикация заблокирована"; fi
exit $code
