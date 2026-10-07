#!/bin/bash
# Тест проверки покрытия: список с дырой обязан блокироваться.
# Проверка, ни разу не заблокировавшая плохой вход, проверкой не является.
set -u
cd "$(dirname "$0")/.." || exit 1
tmp=$(mktemp -d)
cp -r . "$tmp/contour" 2>/dev/null
cd "$tmp/contour" || exit 1
head -n -2 SHA256SUMS > sums.tmp && mv sums.tmp SHA256SUMS
out=$(bash scripts/verify.sh 2>&1); code=$?
rm -rf "$tmp"
if [ "$code" -eq 1 ] && printf '%s' "$out" | grep -q 'ДЫРА В СПИСКЕ'; then
  echo "OK: дыра в списке заблокирована (exit 1)"
  exit 0
fi
echo "FAIL: проверка не заблокировала список с дырой (exit $code)"; exit 1
