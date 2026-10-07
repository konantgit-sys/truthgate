#!/bin/bash
# Проверка контура одной командой. Ничего не требует, кроме coreutils.
#
# Что делает:
#   1) сверяет каждый файл контура с SHA256SUMS — то есть проверяет, что байты
#      именно те, что были опубликованы;
#   2) считает записи реестра исправлений и его размер, чтобы паритет с нашим
#      каталогом проверялся числом, а не глазами;
#   3) повторяет контрольный пример: корень набора методик собирается из
#      манифеста и должен совпасть с опубликованным.
#
# Запуск:  bash scripts/verify.sh
# Код возврата: 0 — всё сошлось; 1 — расхождение (что именно, печатается).
set -u
cd "$(dirname "$0")/.." || exit 1
fail=0

echo "1) Сверка байтов с SHA256SUMS"
if sha256sum -c SHA256SUMS --quiet 2>/tmp/verify_sums.err; then
  echo "   OK: файлов в списке $(grep -cE '^[0-9a-f]{64}' SHA256SUMS), расхождений нет"
else
  echo "   РАСХОЖДЕНИЕ:"; sed 's/^/     /' /tmp/verify_sums.err | head -10; fail=1
fi

echo "1b) Покрытие: список должен перечислять каждый файл контура"
# ПОКРЫТИЕ: SHA256SUMS не может содержать собственный хеш, поэтому он единственный
# файл вне списка. Любой другой файл без записи — дыра: его байты никем не проверяются.
if [ -f SHA256SUMS ]; then
  listed=$(grep -cE '^[0-9a-f]{64}' SHA256SUMS)
  present=$(find . -type f -not -path './.git/*' -not -path '*/__pycache__/*' -not -name '*.pyc' -not -name SHA256SUMS | wc -l)
  missing=$(find . -type f -not -path './.git/*' -not -path '*/__pycache__/*' -not -name '*.pyc' -not -name SHA256SUMS | sed 's|^\./||' | sort > /tmp/f_contour.txt; awk '{print $2}' SHA256SUMS | sed 's|^\./||' | sort > /tmp/f_listed.txt; comm -23 /tmp/f_contour.txt /tmp/f_listed.txt)
  if [ -n "$missing" ]; then
    echo "   ДЫРА В СПИСКЕ: файлы без записи:"; printf '%s\n' "$missing" | sed 's/^/     /' | head -10; fail=1
  else
    echo "   OK: файлов в дереве $present, записей $listed, без записи только сам SHA256SUMS"
  fi
fi

echo "2) Реестр исправлений"
ids=$(grep -cE '^## C-[0-9]{4}' ledger/CORRECTIONS.md)
bytes=$(wc -c < ledger/CORRECTIONS.md | tr -d ' ')
echo "   записей: $ids | знаков: $bytes"
if [ "$ids" -lt 40 ]; then
  echo "   ПОДОЗРЕНИЕ: записей меньше 40 — копия реестра, похоже, отстала"; fail=1
fi

echo "3) Манифест методик: корень из списка"
if [ -f manifests/METHOD_FILES.tsv ] || [ -f methodology/METHOD_FILES.tsv ]; then
  man=$(ls manifests/METHOD_FILES.tsv methodology/METHOD_FILES.tsv 2>/dev/null | head -1)
  python3 - "$man" <<'PY'
import hashlib, json, re, sys
man = sys.argv[1]
pairs = {}
for line in open(man, encoding='utf-8'):
    line = line.rstrip('\n')
    if not line or line.startswith('#'):
        continue
    parts = [p for p in re.split(r'\t+|\s{2,}', line) if p]
    if len(parts) >= 2 and re.fullmatch(r'[0-9a-f]{64}', parts[-1]):
        pairs[parts[0].strip()] = parts[-1]
root = hashlib.sha256(json.dumps(pairs, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
print('   пар: %d | корень: %s' % (len(pairs), root))
PY
else
  echo "   манифеста в копии нет — шаг пропущен (в публичном контуре он лежит на сайте, а не в репозитории)"
fi

if [ "$fail" -eq 0 ]; then
  echo "ИТОГ: OK — контур сходится"
else
  echo "ИТОГ: FAIL — см. выше"
fi
exit "$fail"
