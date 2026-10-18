#!/bin/bash
# Универсальный шлюз перед ЛЮБОЙ публикацией вывода с цифрами.
# Общий модуль — вызывается из борды, отчётов, документов и любых проектов.
#
#   gate.sh <draft.md> <facts.json>
#
# exit 0 — PASS (числа сверены с прогоном), публиковать можно
# exit 1 — FAIL без опознанной причины (резерв; в норме не встречается)
# exit 2 — неверный вызов: не переданы аргументы
# exit 10 — нет файла черновика
# exit 11 — нет файла фактов
# exit 12 — шапка Role/Post type/Data status/Conflict или метки не в порядке
# exit 13 — нет знаменателя   |  exit 14 — контроль без исполняемого live-блока
# exit 15 — живой контроль не выполнен / расходится / пуст
# exit 16 — в тексте есть числа, которых нет в facts.numbers
# exit 17 — пустой черновик
# exit 18 — текст не совпал с рендером из фактов (число правили руками)
# exit 19 — метка времени расходится с часами
# Таблица кодов — reasons.py --table. Разные причины обязаны быть различимы:
# до 18.10.2026 все отказы возвращали 1, и тест «код не ноль» мог пройти по
# чужой причине, а не по той, которую называл.
#
# Метка пропуска кладётся в TRUTHGATE_PASS_DIR (по умолчанию ~/.truthgate/pass).
# Бордовая обёртка задаёт свой каталог, чтобы reply.py видел ту же метку.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
DRAFT="${1:-}"; FACTS="${2:-}"
if [ -z "$DRAFT" ] || [ -z "$FACTS" ]; then
  echo "ИСПОЛЬЗОВАНИЕ: gate.sh <draft.md> <facts.json>"; exit 2
fi
[ -f "$DRAFT" ] || { echo "✗ нет черновика: $DRAFT"; exit 10; }
[ -f "$FACTS" ] || { echo "✗ НЕТ FACTS: без прогона цифры публиковать нельзя ($FACTS)"; exit 11; }
# Пустой (или из одних пробелов) черновик — это отказ, а не «нет шапки»:
# раньше он падал на header_check и смешивался с отсутствием шапки.
if ! grep -q '[^[:space:]]' "$DRAFT" 2>/dev/null; then
  echo "✗ ПУСТОЙ ЧЕРНОВИК: публиковать нечего"; exit 17
fi

# ── ДОПОЛНИТЕЛЬНЫЙ БАРЬЕР (04.10.2026): шапка Role/Post type/Data status/Conflict
# и метка unreplicated для кампанийных цифр. До этого правило жило в документах
# и проверялось только вниманием: шлюз не проверял ни одного поля шапки.
if ! python3 "$HERE/header_check.py" "$DRAFT"; then
  echo "ШЛЮЗ: CLOSED [12 HEADER] — публикация заблокирована (шапка/метки, см. причины выше)"
  exit 12
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
else echo "ШЛЮЗ: CLOSED — публикация заблокирована (код $code)"; fi
exit $code
