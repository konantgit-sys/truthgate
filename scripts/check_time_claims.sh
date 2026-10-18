#!/bin/bash
# Проверка метки ТЕКУЩЕГО времени в черновике/ответе/докладе.
#
# Зачем v2.0. 04.10.2026 доклад в чат был подписан «ОБСТАНОВКА 11:35 МСК» в 11:07 МСК
# (забег 28 минут), и прежняя версия барьера это НЕ поймала: она искала только
# формулировку «Время HH:MM МСК», а доклад был подписан словом «ОБСТАНОВКА».
# Класс ошибки повторялся четыре раза — значит проверка была нерабочей на дырявом
# входе. Теперь ловятся и метка-маркер (ДОКЛАД/ОТЧЁТ/ОБСТАНОВКА/Сейчас/…), и любая
# метка с «МСК» в шапке документа (первые 400 знаков).
#
# Исторические метки внутри текста (цитаты, seq, прошлые посты) не считаются
# заявлением о текущем времени: они не попадают ни под маркеры, ни в шапку.
#
# Использование:
#   bash scripts/check_time_claims.sh <file>      # проверить
#   bash scripts/check_time_claims.sh --stamp     # выдать метку для вставки в доклад
#   bash scripts/check_time_claims.sh --stdin     # прочитать текст из stdin
#
# Порог расхождения: 5 минут. exit 0 = PASS, exit 1 = FAIL, exit 2 = нет входа.
CWD_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # путь считается от файла, а не от узла автора
NOWH="$(bash "$CWD_DIR/scripts/now_msk.sh" 2>/dev/null)"
[ -n "$NOWH" ] || NOWH="$(TZ=Europe/Moscow date '+%H:%M')"

if [ "$1" = "--stamp" ]; then
    echo "$NOWH" | grep -oE '[0-9]{1,2}:[0-9]{2}' | head -1
    exit 0
fi

MODE="file"
if [ "$1" = "--stdin" ]; then
    MODE="stdin"
    TMP="$(mktemp)"
    cat > "$TMP"
    D="$TMP"
else
    D="$1"
    [ -f "$D" ] || { echo "  нет файла: ${D:-<не передан>}"; exit 2; }
fi

python3 - "$D" "$NOWH" <<'PY'
import re, sys
path, nowh = sys.argv[1], sys.argv[2]
m = re.search(r'(\d{1,2}):(\d{2})', nowh)
nowmin = int(m.group(1))*60 + int(m.group(2))
nowlbl = '%02d:%02d' % divmod(nowmin, 60)
text = open(path, encoding='utf-8').read()

MARKERS = (r'Время|время|ДОКЛАД|Доклад|доклад|ОТЧЁТ|Отчёт|отчёт|ОБСТАНОВКА|Обстановка|'
           r'обстановка|СВОДКА|Сводка|сводка|СЕЙЧАС|Сейчас|сейчас|ИТОГ|Итого|итого|'
           r'СТАРТ|Старт|начат|НАЧАТ|подписан|публикуется|Состояние|состояние|Метка')
PAST = (r'ранее|раньше|прошл|цитат|seq|seq\s*\d|писал|писалось|было|был\b|тогда|вчера|'
        r'до этого|пост|поста|коммит|цитирую|cited|quoted|previously')
claims = {}
for m in re.finditer(r'(?:%s)[^\n]{0,40}?(\d{1,2}):(\d{2})\s*\**\s*МСК' % MARKERS, text):
    h, mi = int(m.group(1)), int(m.group(2))
    back = text[max(0, m.start()-60):m.start()+len(m.group(0))]
    if h <= 23 and mi <= 59 and not re.search(PAST, back, re.IGNORECASE):
        claims.setdefault(h*60+mi, m.start())
# шапка документа: любая метка «HH:MM МСК» в первых 400 знаках, но исторические
# ссылки (с «ранее», «seq», «пост», «коммит» рядом) заявлением о текущем времени не считаются
for m in re.finditer(r'(\d{1,2}):(\d{2})\s*\**\s*МСК', text[:400]):
    h, mi = int(m.group(1)), int(m.group(2))
    back = text[max(0, m.start()-60):m.start()+len(m.group(0))]
    if h <= 23 and mi <= 59 and not re.search(PAST, back, re.IGNORECASE):
        claims.setdefault(h*60+mi, m.start())

if not claims:
    # 17.10.2026, дыра, найденная на публикации 92120: черновик объявлял метку
    # («Метка времени: <незаполненный шаблон> МСК»), парсер её не распознал и
    # трактовал как «метки нет» — exit 0. Объявленная, но нераспознанная метка
    # это отказ, а не отсутствие заявления: иначе подстановка вместо времени
    # проходит проверку молча.
    # Только явное поле метки: «Data window» часто несёт одну дату без времени,
    # и это законно. Шаблон внутри «Data window» ловит проверка truthgate.
    declared = re.search(r'Метка времени', text)
    if declared:
        print('  МЕТКА ОБЪЯВЛЕНА, НО НЕ РАСПОЗНАНА — в тексте есть поле метки, '
              'а времени в формате HH:MM МСК нет (сейчас %s МСК)' % nowlbl)
        print('  ИТОГ: FAIL — объявленную метку обязан нести распознаваемый формат')
        sys.exit(1)
    print('  заявления о текущем времени нет — проверять нечего (сейчас %s МСК)' % nowlbl)
    sys.exit(0)

bad = 0
for c in sorted(claims):
    h, mi = divmod(c, 60)
    delta = c - nowmin
    ok = abs(delta) <= 5
    bad += 0 if ok else 1
    hint = 'совпадает' if ok else ('забег вперёд на %d мин' % delta if delta > 0 else 'отставание на %d мин' % -delta)
    print('  метка %02d:%02d МСК → %s (%s; сейчас %s МСК)' % (h, mi, 'OK' if ok else 'РАСХОЖДЕНИЕ', hint, nowlbl))
print('  ИТОГ: ' + ('PASS — метка в пределах 5 минут' if not bad else 'FAIL — метка вне окна, взять время командой: bash scripts/check_time_claims.sh --stamp'))
sys.exit(1 if bad else 0)
PY
RC=$?
[ "$MODE" = "stdin" ] && rm -f "$TMP"
exit $RC
