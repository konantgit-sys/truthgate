#!/bin/bash
# Тесты проверки покрытия: список с дырой обязан блокироваться, и вложенный
# одноимённый манифест обязан считаться файлом контура, а не «самим SHA256SUMS».
# Проверка, ни разу не заблокировавшая плохой вход, проверкой не является.
# Случай B пришёл извне (борда, seq 78516) и здесь воспроизведён фикстурой.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
fails=0

# --- A. Урезанный список: файл контура без записи обязан блокироваться ---------
tmp=$(mktemp -d)
cp -r "$ROOT" "$tmp/contour"; cd "$tmp/contour" || exit 1
head -n -2 SHA256SUMS > sums.tmp && mv sums.tmp SHA256SUMS
out=$(bash scripts/verify.sh 2>&1); code=$?
cd /; rm -rf "$tmp"
if [ "$code" -eq 1 ] && printf '%s' "$out" | grep -q 'ДЫРА В СПИСКЕ'; then
  echo "OK A: дыра в списке заблокирована (exit 1)"
else
  echo "FAIL A: проверка не заблокировала список с дырой (exit $code)"; fails=$((fails+1))
fi

# --- B. Вложенный SHA256SUMS без записи обязан блокироваться -------------------
# Корневой манифест перечисляет только payload; nested/SHA256SUMS существует и в
# списке не значится. Старый предикат `-not -name SHA256SUMS` выбрасывал его и
# давал ложный PASS.
tmp=$(mktemp -d)
mkdir -p "$tmp/t/nested"
printf 'payload bytes\n' > "$tmp/t/payload"
printf 'unlisted nested manifest\n' > "$tmp/t/nested/SHA256SUMS"
( cd "$tmp/t" && sha256sum payload | sed 's| \*| |' > SHA256SUMS )
# Тест берёт предикат ИЗ САМОГО verify.sh, а не из своей копии: иначе тест
# проверяет сам себя. Хардкод предиката на стороне теста — та же дыра слоем выше.
pred=$(sed -n "s/^  present=\$(find \. \(.*\) | wc -l)$/\1/p" "$ROOT/scripts/verify.sh")
if [ -z "$pred" ]; then echo "FAIL B: предикат покрытия не извлекается из verify.sh"; exit 1; fi
files=$(cd "$tmp/t" && eval "find . $pred" | sed 's|^\./||' | sort | tr '\n' ' ')
old="payload "
if printf '%s' "$files" | grep -q 'nested/SHA256SUMS'; then
  echo "OK B: вложенный манифест виден предикату покрытия"
else
  echo "FAIL B: вложенный манифест невидим предикату покрытия (видно: $files)"; fails=$((fails+1))
fi

if [ "$fails" -eq 0 ]; then echo "ИТОГ: 2 из 2 — оба плохих входа блокируются"; exit 0; fi
echo "ИТОГ: провалено $fails из 2"; exit 1
