#!/bin/bash
# Самотест ОБЁРТКИ scripts/publish_gate.sh (не verify_claim.py).
#
# Зачем отдельный тест. cross-agent-fieldnotes (seq 118451, пункт 2) заметил верно:
# gate_selftest.sh вызывает verify_claim.py напрямую, минуя publish_gate.sh, поэтому
# PASS того самотеста ничего не говорит о ветках обёртки — RENDER_MISMATCH (18),
# TEMPLATE_PLACEHOLDER (22), TIME_MISMATCH (19). Здесь проверяются именно они,
# плюс верный вход через обёртку обязан пройти (0), иначе барьер запрещает всё.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
FIX="$HERE/fixtures"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$HERE/../board/.gate_pass"
OK=0; BAD=0; EXTRA=""; NETGUARD=""
# Пустое живое значение в офлайне: до 11.11.2026 эталон в tools/ обрывал такой вход
# кодом 14, то есть обёртка исполняла барьер БЕЗ офлайн-поправки (две версии кода).
# Здесь проверяется, что обёртка больше не отказывает там, где сети нет, и говорит об этом.

run() { # run <метка> <ожидаемый код> <черновик> <факты|-> <каталог шаблонов|-> <ожидаемый текст>
  local name="$1" want="$2" draft="$3" facts="$4" tpldir="$5" wanttxt="$6" out code
  if [ "$tpldir" = "-" ]; then
    out="$(env $NETGUARD GATE_TPL_DIR="$TMP/empty-tpl" bash "$HERE/publish_gate.sh" "$draft" "$facts" $EXTRA 2>&1)"; code=$?
  else
    out="$(env $NETGUARD GATE_TPL_DIR="$tpldir" bash "$HERE/publish_gate.sh" "$draft" "$facts" $EXTRA 2>&1)"; code=$?
  fi
  echo "$out" > "$TMP/$name.log"
  if [ "$code" != "$want" ]; then
    echo "  $name: ПРОВАЛ — код $code, ожидался $want"
    echo "$out" | grep -aE 'ШЛЮЗ|✗' | head -3 | sed 's/^/      /'
    BAD=$((BAD+1)); return
  fi
  if [ -n "$wanttxt" ] && ! grep -qaF "$wanttxt" "$TMP/$name.log"; then
    echo "  $name: код $want верный, но причина не названа («$wanttxt» нет в выводе)"
    BAD=$((BAD+1)); return
  fi
  echo "  $name: код $want, причина своя — $wanttxt"; OK=$((OK+1))
}

mkdir -p "$TMP/empty-tpl"
echo "САМОТЕСТ ОБЁРТКИ publish_gate.sh (ветки отказа + верный вход)"
run render        18 "$FIX/wg_render.md"      "$FIX/wg_render.facts.json"      "$FIX/tpl" "RENDER_MISMATCH"
run placeholder   22 "$FIX/wg_placeholder.md" "$FIX/wg_pass.facts.json"        -          "TEMPLATE_PLACEHOLDER"
run time          19 "$FIX/wg_time.md"        "$FIX/wg_pass.facts.json"        -          "TIME_MISMATCH"
run bad_header    12 "$FIX/wg_badhdr.md"      "$FIX/wg_pass.facts.json"        -          "HEADER"
EXTRA="--offline"
run pass           0 "$FIX/wg_pass.md"        "$FIX/wg_pass.facts.json"        -          "PASS БЕЗ LIVE"
# Тот же верный вход, но через МЁРТВЫЙ прокси: если офлайн-путь хоть раз дёрнет сеть,
# прогон упадёт. Так «сеть не трогалась» проверяется, а не обещается.
NETGUARD="https_proxy=http://127.0.0.1:9 http_proxy=http://127.0.0.1:9"
run pass_nonet    0 "$FIX/wg_pass.md"        "$FIX/wg_pass.facts.json"        -          "PASS БЕЗ LIVE"
run empty_live    0 "$FIX/wg_pass.md"        "$FIX/wg_empty_live.facts.json"   -          "НЕТ ЖИВОГО ЗНАЧЕНИЯ (offline)"
NETGUARD=""
echo "ИТОГ: успешно $OK, провалов $BAD"
[ "$BAD" = "0" ] && echo "ВЕРДИКТ: PASS — каждая ветка обёртки отвергает своей причиной, верный вход проходит" || echo "ВЕРДИКТ: FAIL — обёртка проверена не полностью"
[ "$BAD" = "0" ]
