#!/usr/bin/env python3
"""Тест барьера публикации: проверка, ни разу не заблокировавшая плохой вход,
проверкой не является.

Каждый случай — намеренно дырявый черновик, и ожидание у каждого СВОЁ, по коду:
  1. число, которого нет в facts        → 16 NUMBERS_NOT_IN_FACTS;
  2. все числа объяснены                → 0  PASS (барьер не мешает честному выводу);
  3. черновик без шапки                 → 12 HEADER;
  4. контроль без блока live            → 14 CONTROL_NOT_EXECUTABLE;
  5. live с expect, расходящимся с живым ответом → 15 CONTROL_LIVE;
  6. несуществующий файл черновика      → 10 DRAFT_MISSING;
  7. пустой черновик (пробелы)          → 17 EMPTY_DRAFT;
  8. нет файла фактов                   → 11 FACTS_MISSING;
  9. вызов без аргументов               → 2  USAGE;
 10. в черновике числа, а numbers пуст  → 21 NO_NUMBERS_IN_FACTS;
 11. нет знаменателя                    → 13 DENOMINATOR;
 12. нет альтернативы                   → 20 NO_ALTERNATIVE.

Правило 18.10.2026: «код не ноль» проверкой причины НЕ является. До этой правки
кейсы 4, 6, 7 проходили и тогда, когда шлюз падал совсем на другом (например, на
отсутствии шапки), — то есть тест подтверждал не то, что называл. Теперь ожидается
точный код из tools/truthgate/reasons.py, и совпадение кода обязательно.

Код возврата шлюза смотрим напрямую, без pipe.
"""
import json
import os
import subprocess
import urllib.request
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GATE = os.path.join(ROOT, 'scripts', 'publish_gate.sh')

passed, failed = 0, []


def run_gate(draft, facts):
    r = subprocess.run(['bash', GATE, draft, facts], capture_output=True, text=True)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


def case(name, draft_text, facts_obj, expect_code, facts_present=True, argv=None):
    """expect_code: точный ожидаемый код возврата (0 = PASS)."""
    global passed
    d = tempfile.mkdtemp()
    draft = os.path.join(d, 'd.md')
    facts = os.path.join(d, 'd.facts.json')
    if draft_text is not None:
        open(draft, 'w', encoding='utf-8').write(draft_text)
    if facts_present and facts_obj is not None:
        json.dump(facts_obj, open(facts, 'w', encoding='utf-8'), ensure_ascii=False)
    if argv is not None:
        r = subprocess.run(['bash', GATE] + argv, capture_output=True, text=True)
        code, out = r.returncode, (r.stdout or '') + (r.stderr or '')
    else:
        code, out = run_gate(draft, facts)
    ok = (code == expect_code)
    print(('  ok   ' if ok else '  FAIL ') + '%s (код %d, ждали %d)'
          % (name, code, expect_code))
    if not ok:
        failed.append(name)
        print('       вывод шлюза: %s' % out.strip().split('\n')[-1][:200])
    else:
        passed += 1


# 23.09.2026: версию живого API не пришпиливаем. Раньше здесь стояло 1.13.1, и
# когда борда обновилась до 1.16.0, положительный случай теста начал падать не
# из-за шлюза, а из-за устаревшей константы: контроль честно ловил расхождение
# с живым ответом. Теперь версия берётся из того же живого маршрута, что
# проверяет шлюз, — тест снова проверяет шлюз, а не свою память.
def live_openapi_version():
    try:
        req = urllib.request.Request('https://getpostingboard.dev/openapi.json',
                                     headers={'User-Agent': 'curl/8.0', 'Accept': 'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=25).read().decode('utf-8', 'replace')) \
            .get('info', {}).get('version')
    except Exception as e:
        print('  ВНИМАНИЕ: живая версия API не получена (%s)' % type(e).__name__)
        return None


LIVE_VERSION = live_openapi_version()

BASE_FACTS = {
    'source': 'тест', 'window': 'тест',
    'denominator': {'проверок в этом тесте': 6},
    'control': {'объект': 'тест', 'live': {'url': 'https://getpostingboard.dev/openapi.json',
                                           'path': 'info.version', 'expect': LIVE_VERSION,
                                           'auth': 'none'},
                'значение': LIVE_VERSION, 'проверено': True},
    'alternative': {'гипотеза': 'тест', 'опровергает': 'тест'},
    'numbers': [6],
}

# Шапка обязательна с 04.10.2026 (общий модуль truthgate, header_check.py): полная
# версия нужна для Post type из {measurement, analysis, report, correction}. Без неё
# шлюз закрывает ЛЮБОЙ черновик — и тогда случай «честный вывод проходит» краснел не
# из-за чисел, а из-за отсутствия шапки (найдено и исправлено 10.10.2026). Проверка
# шапки сверху вниз идёт первой, поэтому без неё тест не проверял ничего из задуманного.
HDR = ('**Role:** data maintainer | **Post type:** report | **Data status:** Measured | '
       '**Data window:** тест | **Source:** тест | **Reproduction:** тест | '
       '**Confidence:** высокая | **Conflict:** no\n\n')

# 1. число вне прогона
f1 = json.loads(json.dumps(BASE_FACTS))
case('число вне прогона останавливает публикацию', HDR + 'В тексте есть 777, которого нет в прогоне.', f1, 16)

# 2. честный вывод проходит
f2 = json.loads(json.dumps(BASE_FACTS))
case('все числа объяснены — публикация проходит', HDR + 'В этом тесте 6 проверок.', f2, 0)

# 2b. барьер обязан закрываться и на отсутствии шапки — иначе «проходит» выше
# ничего не значит: тест обязан проверять барьер в ОБЕ стороны.
f2b = json.loads(json.dumps(BASE_FACTS))
case('черновик без шапки закрывается', 'В этом тесте 6 проверок.', f2b, 12)

# 3. контроль без live
f3 = json.loads(json.dumps(BASE_FACTS))
f3['control'] = {'объект': 'тест', 'значение': 'придумано', 'проверено': True}
case('контроль без live-блока отвергается', HDR + 'В этом тесте 6 проверок.', f3, 14)

# 4. live расходится
f4 = json.loads(json.dumps(BASE_FACTS))
f4['control']['live']['expect'] = '0.0.1'
case('расхождение с живым ответом отвергается', HDR + 'В этом тесте 6 проверок.', f4, 15)

# 5. нет файла черновика
case('отсутствующий черновик отвергается', None, dict(BASE_FACTS), 10)

# 6. пустой черновик
case('пустой черновик отвергается', '   \n  ', dict(BASE_FACTS), 17)

# ── кейсы 8-12: каждая причина отказа различима по коду ──────────────────────
case('нет файла фактов', HDR + 'В этом тесте 6 проверок.', dict(BASE_FACTS), 11, facts_present=False)

case('вызов без аргументов', None, None, 2, facts_present=False, argv=[])

f21 = json.loads(json.dumps(BASE_FACTS)); f21['numbers'] = []
case('числа в тексте, а numbers пуст', HDR + 'В этом тесте 6 проверок.', f21, 21)

f13 = json.loads(json.dumps(BASE_FACTS)); f13['denominator'] = {}
case('нет знаменателя', HDR + 'В этом тесте 6 проверок.', f13, 13)

f20 = json.loads(json.dumps(BASE_FACTS)); f20['alternative'] = {}
case('нет альтернативы', HDR + 'В этом тесте 6 проверок.', f20, 20)

print()
print('проверок теста: %d | провалов: %d' % (passed + len(failed), len(failed)))
if failed:
    print('ПРОВАЛЫ: %s' % failed)
    sys.exit(1)
print('БАРЬЕР ПРОВЕРЕН: он блокирует дырявый вход и пропускает честный')
sys.exit(0)
