#!/bin/bash
# Обёртка борды над общим шлюзом (в этом репозитории — tools/truthgate/).
#
# Раньше барьер жил здесь целиком; 2026-09-18 он вынесен в общий модуль, чтобы
# работать не только на борде. Поведение сохранено посимвольно по контракту:
# те же exit-коды (0 PASS / 1 FAIL / 2 ошибка вызова) и та же метка пропуска в
# board/.gate_pass — reply.py принимает файл только со свежим PASS оттуда.
#
#   scripts/publish_gate.sh <draft.md> <facts.json>
set -u

# ── ДОПОЛНИТЕЛЬНЫЙ БАРЬЕР: числа в тексте не написаны руками, а собраны из фактов.
# 23.09.2026 тест на дырявом входе показал дыру: подмена «21 первых» на «24 первых»
# проходила как PASS, потому что 24 попало в facts.numbers как токен даты «24.09».
# Список чисел всегда шире одной фразы, поэтому сверка со списком дырявая по природе.
# Теперь для каждого черновика, у которого есть шаблон tpl/<имя>.tpl.md, шлюз собирает
# текст из тех же фактов заново и требует посимвольного совпадения с публикуемым файлом.
# Подмена любого числа руками = расхождение с рендером = публикация заблокирована.
HERE_DIR="$(cd "$(dirname "$0")" && pwd)"
DRAFT_ARG="${1:-}"; FACTS_ARG="${2:-}"
if [ -n "$DRAFT_ARG" ] && [ -n "$FACTS_ARG" ] && [ -f "$DRAFT_ARG" ]; then
  TPL="$HERE_DIR/../board/replies/tpl/$(basename "$DRAFT_ARG" .md).tpl.md"
  if [ -f "$TPL" ]; then
    if ! python3 "$HERE_DIR/render_draft.py" --template "$TPL" --facts "$FACTS_ARG" --check "$DRAFT_ARG"; then
      echo "ШЛЮЗ: CLOSED [18 RENDER_MISMATCH] — текст не совпал с рендером из фактов (число правили руками?)"
      exit 18
    fi
  elif grep -qE '\{\{[^}]+\}\}' "$DRAFT_ARG"; then
    echo "ШЛЮЗ: CLOSED [22 TEMPLATE_PLACEHOLDER] — в черновике остались неподставленные {{ключи}}, шаблона нет"
    exit 22
  fi
fi
# === ⏱ метка времени внутри черновика: число из замера, а не из головы ===
if [ -n "$DRAFT_ARG" ] && [ -f "$DRAFT_ARG" ]; then
  if ! bash "$HERE_DIR/check_time_claims.sh" "$DRAFT_ARG"; then
    echo "ШЛЮЗ: CLOSED [19 TIME_MISMATCH] — метка времени в тексте расходится с часами"
    exit 19
  fi
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
# Модуль ищется так: сначала рядом с репозиторием (вложенная копия tools/truthgate,
# которую можно скачать вместе с кодом), затем в рабочем дереве на два уровня выше.
# Правка 18.10.2026 по внешнему разбору (seq 92850): прежний путь был жёстко задан
# абсолютным адресом узла, поэтому скачанный репозиторий не мог прогнать свой же тест.
# Порядок: явная переменная → вложенная копия рядом → рабочее дерево → абсолютный резерв узла.
if [ -n "${TRUTHGATE_DIR:-}" ]; then TRUTHGATE="$TRUTHGATE_DIR"
elif [ -f "$HERE/../tools/truthgate/gate.sh" ]; then TRUTHGATE="$(cd "$HERE/../tools/truthgate" && pwd)"
elif [ -f "$HERE/../../tools/truthgate/gate.sh" ]; then TRUTHGATE="$(cd "$HERE/../../tools/truthgate" && pwd)"
elif [ -f "$HOME/.truthgate/gate.sh" ]; then TRUTHGATE="$HOME/.truthgate"
else echo "ШЛЮЗ: ОШИБКА — модуль truthgate не найден"; exit 2; fi
export TRUTHGATE_PASS_DIR="$HERE/../board/.gate_pass"
exec bash "$TRUTHGATE/gate.sh" "$@"
