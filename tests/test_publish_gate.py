#!/usr/bin/env python3
"""Тест барьера публикации: проверка, ни разу не заблокировавшая плохой вход,
проверкой не является.

Каждый случай — намеренно дырявый черновик, и ожидание у каждого своё:
  1. число, которого нет в facts → FAIL (барьер обязан остановить);
  2. все числа объяснены → PASS (барьер не должен блокировать честный вывод);
  3. контроль без блока live → FAIL (слово «проверено» контролем не считается);
  4. live с expect, расходящимся с живым ответом → FAIL;
  5. несуществующий файл черновика → FAIL, а не тихий PASS;
  6. пустой черновик → FAIL (нечего публиковать).

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


def case(name, draft_text, facts_obj, expect_zero, facts_present=True):
    global passed
    d = tempfile.mkdtemp()
    draft = os.path.join(d, 'd.md')
    facts = os.path.join(d, 'd.facts.json')
    if draft_text is not None:
        open(draft, 'w', encoding='utf-8').write(draft_text)
    if facts_present and facts_obj is not None:
        json.dump(facts_obj, open(facts, 'w', encoding='utf-8'), ensure_ascii=False)
    code, out = run_gate(draft, facts)
    ok = (code == 0) if expect_zero else (code != 0)
    print(('  ok   ' if ok else '  FAIL ') + '%s (код %d, ждали %s)'
          % (name, code, '0' if expect_zero else 'не 0'))
    if not ok:
        failed.append(name)
        print('       вывод шлюза: %s' % out.strip().split('\n')[-1][:200])
        passed -= 0
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
case('число вне прогона останавливает публикацию', HDR + 'В тексте есть 777, которого нет в прогоне.', f1, False)

# 2. честный вывод проходит
f2 = json.loads(json.dumps(BASE_FACTS))
case('все числа объяснены — публикация проходит', HDR + 'В этом тесте 6 проверок.', f2, True)

# 2b. барьер обязан закрываться и на отсутствии шапки — иначе «проходит» выше
# ничего не значит: тест обязан проверять барьер в ОБЕ стороны.
f2b = json.loads(json.dumps(BASE_FACTS))
case('черновик без шапки закрывается', 'В этом тесте 6 проверок.', f2b, False)

# 3. контроль без live
f3 = json.loads(json.dumps(BASE_FACTS))
f3['control'] = {'объект': 'тест', 'значение': 'придумано', 'проверено': True}
case('контроль без live-блока отвергается', HDR + 'В этом тесте 6 проверок.', f3, False)

# 4. live расходится
f4 = json.loads(json.dumps(BASE_FACTS))
f4['control']['live']['expect'] = '0.0.1'
case('расхождение с живым ответом отвергается', 'В этом тесте 6 проверок.', f4, False)

# 5. нет файла черновика
case('отсутствующий черновик отвергается', None, dict(BASE_FACTS), False)

# 6. пустой черновик
case('пустой черновик отвергается', '   \n  ', dict(BASE_FACTS), False)

print()
print('проверок теста: %d | провалов: %d' % (passed + len(failed), len(failed)))
if failed:
    print('ПРОВАЛЫ: %s' % failed)
    sys.exit(1)
print('БАРЬЕР ПРОВЕРЕН: он блокирует дырявый вход и пропускает честный')
sys.exit(0)
