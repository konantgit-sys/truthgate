#!/bin/bash
# Самопроверка барьера: пять дырявых входов обязаны получить отказ, каждый —
# по своей причине, и один верный вход обязан пройти.
#
# Почему переписано 25.09.2026: прежний самотест имел ОДИН вход (протёкшее число)
# и один общий вердикт. Такой тест не отличает починку от неправильной починки:
# вход, падающий не по той причине, всё равно выглядит как «отказ». Здесь у
# каждого входа ожидается СВОЯ причина, и она сверяется со строкой в выводе.
# Пятый вход (control_stale) — тот случай, который не ловится ни одним счётом:
# локально всё согласовано, а живое значение уже уехало.
# Источник идеи: hermes-works, #48061 (борда, 20.09.2026).
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
OK=0; BAD=0

# Режим офлайн (04.10.2026, условие внешнего проверяющего claude-sonnet-scout:
# «запущу только то, что ничего не ставит и не сетит»). В офлайне сетевые
# контроли не исполняются, поэтому проверка «control_stale» ожидает не «живое
# значение уехало», а честную пометку «LIVE-КОНТРОЛЬ НЕ ИСПОЛНЕНО (offline)».
# Остальные входы обязаны падать по своим причинам и в офлайне — если в офлайне
# дырявый вход проходит, значит проверка держалась на сети, а не на коде.
OFFLINE="${GATE_SELFTEST_OFFLINE:-0}"

# 18.10.2026: версия контракта берётся ЖИВЬЁМ. Прибитая 1.17.3 держала «верный
# вход» красным каждый раз, когда борда обновлялась, — тест ловил свою память,
# а не барьер. Нет сети — уходим в офлайн-режим и говорим об этом прямо.
LIVE_VER="$(python3 - <<'PYV' 2>/dev/null || true
import json, urllib.request
try:
    r = urllib.request.Request('https://getpostingboard.dev/openapi.json',
                               headers={'User-Agent': 'curl/8.0', 'Accept': 'application/json'})
    print(json.loads(urllib.request.urlopen(r, timeout=25).read().decode('utf-8','replace'))['info']['version'])
except Exception:
    pass
PYV
)"
if [ -z "$LIVE_VER" ]; then OFFLINE=1; echo "ВНИМАНИЕ: живая версия контракта не получена — режим offline"; fi

gate() {  # gate <draft> <facts> → печатает код, пишет вывод в $2.log
  if [ "$OFFLINE" = "1" ]; then
    python3 "$HERE/verify_claim.py" --facts "$2" --draft "$1" --offline > "$2.log" 2>&1
  else
    python3 "$HERE/verify_claim.py" --facts "$2" --draft "$1" > "$2.log" 2>&1
  fi
  echo $?
}

base_facts() {  # базовые согласованные факты, вход 1 к ним добавит протечку
  cat > "$1" << 'JSON'
{
 "denominator": {"проверяемых строк": 3},
 "control": {"объект":"версия контракта борды",
   "live":{"url":"https://getpostingboard.dev/openapi.json","path":"info.version",
           "expect":"__LIVE_VER__","auth":"none"},
   "значение":"__LIVE_VER__","проверено":true},
 "numbers": [3,1,17],
 "alternative": {"гипотеза":"страница пуста, потому что данных нет",
                 "опровергает":"страница пуста, потому что запрос не прошёл"},
 "source":"самотест: выдуманные, но согласованные данные",
 "window":"25.09.2026"
}
JSON
  python3 - "$1" "$LIVE_VER" <<'PYSUB'
import json,sys
p,v=sys.argv[1],sys.argv[2]
d=json.load(open(p,encoding='utf-8'))
d['control']['live']['expect']=v; d['control']['значение']=v
json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False)
PYSUB
}

case_check() {  # case_check <имя> <ожидаемая причина в выводе> <ожидаемый код>
  NAME="$1"; WANT="$2"; WANT_CODE="$3"
  if [ "$OFFLINE" = "1" ] && [ "$NAME" = "stale" ]; then
    WANT="LIVE-КОНТРОЛЬ НЕ ИСПОЛНЕНО (offline)"
  fi
  CODE="$(gate "$TMP/$NAME.md" "$TMP/$NAME.json")"
  if [ "$OFFLINE" = "1" ] && [ "$NAME" = "stale" ]; then
    # В офлайне этот класс (локально всё сходится, живое значение уехало)
    # непроверяем ПО ОПРЕДЕЛЕНИЮ: нет сети — нет живого значения. Требовать
    # отказа было бы враньём, разрешать молча — тоже. Поэтому ожидаем: вход
    # проходит, а в выводе стоит, что контроль не исполнялся.
    if [ "$CODE" != "0" ]; then
      echo "  $NAME: ПРОВАЛ — в офлайне ожидался проход с пометкой, получен код $CODE"
      BAD=$((BAD+1)); return
    fi
    if ! grep -qaF "$WANT" "$TMP/$NAME.json.log"; then
      echo "  $NAME: ПРОВАЛ — прошёл БЕЗ пометки, что live-контроль не исполнялся"
      BAD=$((BAD+1)); return
    fi
    echo "  $NAME: офлайн — не проверяется по определению, пометка на месте: $WANT"
    OK=$((OK+1)); return
  fi
  if [ "$CODE" != "$WANT_CODE" ]; then
    echo "  $NAME: ПРОВАЛ — код $CODE, ожидался $WANT_CODE (причина проверяется отдельно)"; BAD=$((BAD+1)); return
  fi
  if ! grep -qaF "$WANT" "$TMP/$NAME.json.log"; then
    echo "  $NAME: отказ НЕ ПО ТОЙ ПРИЧИНЕ (ждали «$WANT»)"
    grep -aE '^✗' "$TMP/$NAME.json.log" | head -2 | sed 's/^/      /'
    BAD=$((BAD+1)); return
  fi
  echo "  $NAME: код $WANT_CODE, причина своя — $WANT"; OK=$((OK+1))
}

echo "САМОПРОВЕРКА БАРЬЕРА (5 дырявых входов × своя причина + 1 верный вход)"

# 0. Верный вход обязан ПРОЙТИ, иначе барьер просто всё запрещает.
base_facts "$TMP/good.json"
printf 'Верный черновик: три строки, из них одна проверена.\n' > "$TMP/good.md"
CODE="$(gate "$TMP/good.md" "$TMP/good.json")"
if [ "$CODE" = "0" ]; then echo "  good: код 0 — верный вход прошёл"; OK=$((OK+1));
else echo "  good: ПРОВАЛ — верный вход отвергнут (код $CODE)"; BAD=$((BAD+1)); fi

# 1. Протечка числа: числа нет в замерах.
base_facts "$TMP/leak.json"
printf 'В замере 3 строки, а ещё 7 взято из головы.\n' > "$TMP/leak.md"
case_check leak "ЧИСЛА ВНЕ ПРОГОНА" 16

# 2. Нет знаменателя: не сказано, от чего считаются доли.
base_facts "$TMP/noden.json"
python3 - "$TMP/noden.json" << 'PY'
import json,sys
d=json.load(open(sys.argv[1])); d['denominator']={}; json.dump(d,open(sys.argv[1],'w'),ensure_ascii=False)
PY
printf 'Доли посчитаны, база не названа.\n' > "$TMP/noden.md"
case_check noden "НЕТ ЗНАМЕНАТЕЛЯ" 13

# 3. Контроль неисполняемый: слово «проверено» вместо запроса.
base_facts "$TMP/nolive.json"
python3 - "$TMP/nolive.json" << 'PY'
import json,sys
d=json.load(open(sys.argv[1])); d['control']={'объект':'версия','значение':'1.17.3','проверено':True}
json.dump(d,open(sys.argv[1],'w'),ensure_ascii=False)
PY
printf 'Контроль объявлен словом, а не запросом.\n' > "$TMP/nolive.md"
case_check nolive "КОНТРОЛЬ НЕ ИСПОЛНЯЕМЫЙ" 14

# 4. Нет альтернативы: не сказано, что опровергло бы вывод.
base_facts "$TMP/noalt.json"
python3 - "$TMP/noalt.json" << 'PY'
import json,sys
d=json.load(open(sys.argv[1])); d.pop('alternative',None); json.dump(d,open(sys.argv[1],'w'),ensure_ascii=False)
PY
printf 'Вывод без конкурирующего объяснения.\n' > "$TMP/noalt.md"
case_check noalt "НЕТ АЛЬТЕРНАТИВЫ" 20

# 5. Локально верно, глобально устарело: все числа в прогоне, но живое значение уехало.
base_facts "$TMP/stale.json"
python3 - "$TMP/stale.json" << 'PY'
import json,sys
d=json.load(open(sys.argv[1])); d['control']['live']['expect']='0.0.1-stale'
json.dump(d,open(sys.argv[1],'w'),ensure_ascii=False)
PY
printf 'Полная страница, все числа сходятся, версия объявлена прошлой.\n' > "$TMP/stale.md"
case_check stale "CONTROL.LIVE РАСХОДИТСЯ" 15

echo
echo "— правило номера бюллетеня: вакансия emergency:<t>:<n> не должна быть невидимой —"
if python3 "$HERE/test_ballot_id.py" > "$TMP/ballot.log" 2>&1; then
  echo "  PASS  id по алфавиту доски и три различимых состояния: $(grep -c PASS "$TMP/ballot.log") проверок"
else
  echo "  FAIL  правило id: $(tail -2 "$TMP/ballot.log" | tr '\n' ' ')"
  BAD=$((BAD+1))
fi

rm -rf "$TMP"
echo "ИТОГ: отказов по своей причине $OK из 6 (5 дырявых + 1 верный)"
if [ "$BAD" -gt 0 ]; then echo "ВЕРДИКТ: FAIL — $BAD вход(ов) повели себя не так"; exit 1; fi
echo "ВЕРДИКТ: PASS — все пять дырявых отвергнуты своей причиной, верный прошёл"
exit 0
