#!/bin/bash
# Прогон всего набора проверок борды. Зачем: 24.09.2026 выяснилось, что тесты не
# запускал никто, и один из них оставался красным незамеченным — он распаковывал
# два значения там, где функция отдаёт три. Красный тест без прогона = его нет.
# Пишет построчно exit-код каждой проверки, в конце — список красных.
cd "$(dirname "$0")/.." || exit 2
fail=0; total=0
# Правка 04.10.2026: при пустом каталоге tests/ glob не раскрывался, python получал
# литерал «../tests/test_*.py» и набор уходил в КРАСНЫЙ по причине, которой нет.
# Отсутствие набора — это «пропущено», а не «сломано»: иначе красный перестаёт
# что-либо значить, и настоящая поломка тонет в ложной.
shopt -s nullglob
matches=("../tests"/test_*.py)
if [ ${#matches[@]} -eq 0 ]; then
  printf '%-38s %s\n' "tests/" "ПРОПУЩЕНО (файлов нет)"
else
  for t in "${matches[@]}"; do
    total=$((total+1))
    out=$(timeout 120 /usr/bin/python3 "$t" 2>&1); code=$?
    word=OK; [ "$code" -ne 0 ] && { word=КРАСНЫЙ; fail=$((fail+1)); }
    printf '%-38s %s (exit=%s)\n' "$(basename "$t")" "$word" "$code"
    [ "$code" -ne 0 ] && printf '%s\n' "$out" | tail -3
  done
fi
# Профиль полномочий и типы вкладов: файл, который заявляет о нас то, чего раньше
# проверить было нечем. Добавлен 04.10.2026 вместе с самими файлами.
total=$((total+1))
out=$(timeout 60 /usr/bin/python3 scripts/test_public_profile.py 2>&1); code=$?
word=OK; [ "$code" -ne 0 ] && { word=КРАСНЫЙ; fail=$((fail+1)); }
printf '%-38s %s (exit=%s)\n' "test_public_profile.py" "$word" "$code"
[ "$code" -ne 0 ] && printf '%s\n' "$out" | tail -3

echo "ИТОГ: проверок $total, красных $fail | $(TZ=Europe/Moscow date '+%d.%m.%Y %H:%M МСК')"
exit $fail

bash scripts/test_sums_coverage.sh || exit 1
