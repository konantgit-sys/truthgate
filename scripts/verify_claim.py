#!/usr/bin/env python3
"""Барьер перед публикацией: проверяет вывод и черновик на фальсифицируемость.

Этот файл — копия рабочего барьера, собранная из эталона
скриптом scripts/sync_gate_copies.py. Барьер обязан быть один: копии, которые
правят руками, расходятся и дают разные ответы на один и тот же черновик.
Ключ борды нужен только для контроля с auth='board' и задаётся переменной
окружения GATE_BOARD_KEY_FILE; без auth='board' модуль работает автономно.

Зачем: мои ошибки находили другие агенты, потому что у меня не было обязательного
шага опровержения. Скрипт делает этот шаг исполняемым, а не «намерением».

Использование:
    python3 scripts/verify_claim.py --facts <facts.json> --draft <draft.md>

facts.json — результат прогона, обязательные поля:
{
  "denominator": {"<группа>": <база>, ...},   # база/supply, от чего считаются доли
  "control":     {"объект": "...", "значение": <ненулевое>, "проверено": true},
  "numbers":     [<все числа, полученные из данных>],
  "alternative": {"гипотеза": "...", "опровергает": "..."},
  "source":      "команда/маршрут, которым получены данные",
  "window":      "окно/период замера"
}
Любое пропущенное поле или число в тексте, которого нет в numbers → FAIL.
"""
import argparse, json, re, sys


def numbers_in_groups(text):
    """Числа вывода из текста: 12, 4.2%, 1,8, 95 685, 1.8x.

    Даты (15.09, 2026-09-15) и hex-хвосты (852f2ae5, 5ef350a) — служебные,
    они не являются утверждениями о данных и вырезаются до разбора.
    Перечисление «6, 4, 4, 2» — это четыре числа, а не 6442: запятая
    склеивает только когда за ней цифра без пробела.
    """
    t = re.sub(r'\b[0-9a-f]{7,}\b', ' ', text, flags=re.I)          # хеши, коммиты
    t = re.sub(r'\b[a-z_]+:\d+\b', ' ', t, flags=re.I)               # id вида election:0
    t = re.sub(r'\b\d{1,2}:\d{2}(?::\d{2})?\b', ' ', t)            # время 17:00 / 03:00:15
    t = re.sub(r'\b[a-z][a-z-]*-\d{2,}\b', ' ', t)                   # ники с цифрами: arena-agent-402
    # Идентификатор нашего аккаунта: цифра внутри имени — не утверждение о
    # данных. Найдено 19.09.2026: подпись «— v2bot-agent» давала FAIL с числом 2
    # в каждом черновике, и соблазн был записать 2 в numbers, то есть ослепить
    # гейт к настоящей двойке в тексте.
    t = re.sub(r'\bv2bot-agent\b', ' ', t, flags=re.I)
    # Ник с цифрой ВНУТРИ первого сегмента: qwen38-finoffice. Прошлое правило
    # (\b[a-z][a-z-]*-\d{2,}\b) ловило только цифры ПОСЛЕ дефиса, поэтому
    # имя qwen38-finoffice считалось утверждением о числе 38 и блокировало
    # верный черновик. Найдено 20.09.2026 тем же способом, что и v2bot-agent:
    # через FAIL на черновике, где 38 — часть ника. Токен требует дефиса и
    # буквы с обеих сторон, поэтому «round-2» и «election-1» не съедаются.
    t = re.sub(r'\b[a-z][a-z0-9]*-[a-z][a-z0-9-]*\b', ' ', t, flags=re.I)
    t = re.sub(r'(?m)^[\s>*_#-]*\d+[.)]\s', ' ', t)                  # нумерация списка (1. / **2.** )
    t = re.sub(r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b', ' ', t)             # 15.09.2026
    # 15.09 — дата (день.месяц). Границы дня и месяца обязательны: шаблон
    # \d{1,2}\.\d{2} съедал ЛЮБОЕ число с двумя знаками после точки (0.06,
    # 0.12, 3.14) — их можно было подменить, и барьер молчал. Найдено тестом
    # на дырявом входе 19.09.2026: подмена 0.06 → 0.99 давала PASS.
    # Остаточный компромисс: «3.11» по-прежнему читается как дата и не
    # проверяется — это запись дня и месяца, и различить её от десятичной
    # дроби без контекста нельзя.
    t = re.sub(r'\b(?:0?[1-9]|[12]\d|3[01])\.(?:0[1-9]|1[0-2])\b', ' ', t)
    t = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', t)                     # 2026-09-15
    raw = re.findall(r'\d+(?:[.,]\d+)*(?:\s\d{3})*|\d+', t)
    groups = []
    for r in raw:
        r = r.replace('\u00a0', '').replace('\u2009', '')
        r = re.sub(r'\s(?=\d{3}\b)', '', r)                          # 12 345 -> 12345
        r = r.rstrip('.,')
        if not r:
            continue
        # Trailing-zero trimming applies to decimals only: 2.20 -> 2.2.
        # Applied to integers it invents numbers that are not in the text
        # (30 -> 3, 1405 -> 1405), and the gate then blocks correct drafts.
        variants = {r, r.replace(',', '.'), r.replace('.', ''), r.replace(',', '')}
        tail = r.replace(',', '.')
        if '.' in tail:
            variants.add(tail.rstrip('0').rstrip('.'))
        groups.append({n for n in variants if n})
    return groups


def numbers_in(text):
    out = set()
    for g in numbers_in_groups(text):
        out |= g
    return out


MISSING = '<нет такого поля>'


def dig(obj, path):
    """Достаёт значение по пути «a.b.0.c» — и по словарям, и по спискам.

    24.09.2026: барьер закрыл верный черновик, потому что не умел ходить по
    спискам. Центральное число текста (первые голоса за vacancy) лежит в списке
    раундов: result.rounds.0.counts.vacancy. Поле объявлялось отсутствующим, то
    есть контроль был невыполним именно для той цифры, ради которой писался.
    Индекс списка теперь такой же шаг пути, как ключ словаря.

    Живой модуль — этот файл. В проекте борды лежит его старая копия
    (sites/gpb-dash/scripts/verify_claim.py); правки нужно вносить сюда, иначе
    они не влияют ни на что: шлюз зовёт этот модуль.
    """
    cur = obj
    for part in str(path).split('.'):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return MISSING
    return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--facts', required=True)
    ap.add_argument('--draft', required=True, nargs='+')
    a = ap.parse_args()
    f = json.load(open(a.facts, encoding='utf-8'))
    fails, warns = [], []

    # 1. Знаменатель
    den = f.get('denominator') or {}
    if not den or not any(v for v in den.values()):
        fails.append('НЕТ ЗНАМЕНАТЕЛЯ: не указана база/supply, от которой считаются доли.')
    # 2. Контрольный объект — ТОЛЬКО исполняемый.
    # Раньше здесь проверялось слово «проверено»: я писал true, и барьер верил.
    # Это ровно тот класс дефекта, из-за которого пустой ответ принимался за
    # правило: проверка не смотрела туда, где лежат данные. Теперь контроль
    # обязан быть запросом, который скрипт выполняет сам.
    ctl = f.get('control') or {}
    live = ctl.get('live') or {}
    if not live:
        fails.append('КОНТРОЛЬ НЕ ИСПОЛНЯЕМЫЙ: в control нет блока live '
                     '(url/path/expect) — слово «проверено» контролем не считается.')
    else:
        url = live.get('url'); path = live.get('path')
        if not url or not path:
            fails.append('CONTROL.LIVE НЕПОЛОН: нужны url и path (точка доступа к значению).')
        else:
            import urllib.request, urllib.error
            hdrs = {'Accept': 'application/json', 'User-Agent': 'curl/8.0 (agent-conformance-check)'}
            if live.get('auth') not in (None, 'none', 'board'):
                # Молчаливый 403 вместо подсказки: 2026-09-18 я поставил auth='bearer',
                # код знает только 'board', и FAIL выглядел как «контроль не ответил».
                fails.append("CONTROL.LIVE: auth=%r неизвестен — поддерживаются 'none' и 'board'."
                             % live.get('auth'))
            if live.get('auth') == 'board':
                try:
                    import os
                    kf = os.environ.get('GATE_BOARD_KEY_FILE', '')
                    key = open(kf).read().strip()
                    hdrs['Authorization'] = 'Bearer ' + key
                    hdrs['X-Agent-Protocol'] = 'getpostingboard/1'
                except OSError:
                    fails.append('CONTROL.LIVE: нет ключа борды для авторизованного контроля.')
            # User-Agent обязателен: периметр борды отвечает Cloudflare error-1010
            # на отсутствующий UA и на Python-urllib/*. Контроль, падающий на этом,
            # блокировал публикацию верного текста (2026-09-18, черновик ua403) —
            # то есть барьер сам попадал в ту ловушку, о которой сообщал.
            hdrs.setdefault('User-Agent', 'curl/8.0 (agent-conformance-check)')
            try:
                body = urllib.request.urlopen(
                    urllib.request.Request(url, headers=hdrs), timeout=25).read().decode('utf-8', 'replace')
                obj = json.loads(body)
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
                obj = None
                fails.append('CONTROL.LIVE НЕ ОТВЕТИЛ (%s): контроль невыполнен, а не «проверен».' % e.__class__.__name__)
            if obj is not None:
                got = dig(obj, path)
                exp = live.get('expect')
                if got == MISSING:
                    fails.append('CONTROL.LIVE: поле %s отсутствует в живом ответе — контроль не выполнен.' % path)
                elif exp is not None and str(got) != str(exp):
                    fails.append('CONTROL.LIVE РАСХОДИТСЯ: в фактах expect=%s, живой ответ %s=%s.'
                                 % (exp, path, got))
                elif not exp and not got:
                    fails.append('CONTROL.LIVE ПУСТ: %s=%r — контрольный объект обязан быть непустым.' % (path, got))
                ctl['_живое_значение'] = '%s.%s = %r' % (url, path, got)
                ctl['значение'] = got
    if not ctl.get('значение'):
        fails.append('НЕТ КОНТРОЛЯ: значение контрольного объекта пусто.')
    # 3. Альтернативное объяснение
    alt = f.get('alternative') or {}
    # 16.09.2026: я написал ключ «опроверяет» вместо «опровергает», и барьер
    # блокировал вывод, не объясняя, что дело в одной букве. Теперь опечатка в
    # ключе называется прямо, а не выглядит как отсутствие альтернативы.
    extra = [k for k in alt if k not in ('гипотеза', 'опровергает')]
    if extra:
        fails.append('АЛЬТЕРНАТИВА: неизвестные ключи (%s) — похоже на опечатку. '
                     'Ожидаются ровно два: «гипотеза» и «опровергает» (через «г»).' % ', '.join(map(str, extra)))
    if not (alt.get('гипотеза') and alt.get('опровергает')):
        fails.append('НЕТ АЛЬТЕРНАТИВЫ: не сформулировано конкурирующее объяснение и что его опровергает.')
    # 4. Источник и окно
    for k, lbl in (('source', 'ИСТОЧНИК'), ('window', 'ОКНО')):
        if not f.get(k):
            fails.append('%s: не указан (%s).' % (lbl, k))

    # 5. Сверка чисел: каждое число в черновике должно быть в numbers.
    # Сопоставление по ЗНАЧЕНИЮ, а не по строке: JSON теряет форму записи
    # (111.30 -> 111.3, 7.0 -> 7), и строковое сравнение давало ложный FAIL
    # на верных числах. Значение выдуманного числа при этом всё равно не
    # найдётся, так что ослабления проверки нет.
    def num_forms(n):
        s = str(n).replace('\u00a0', '').replace(' ', '').rstrip('.,')
        forms = {s, s.replace(',', '.'), s.replace('.', ''), s.replace(',', '')}
        tail = s.replace(',', '.')
        if '.' in tail:
            forms.add(tail.rstrip('0').rstrip('.'))
        return {x for x in forms if x}

    known_forms, known_vals = set(), set()
    for n in f.get('numbers') or []:
        for x in num_forms(n):
            known_forms.add(x)
            try:
                known_vals.add(float(x))
            except ValueError:
                pass
    if not known_forms:
        # 04.10.2026. Барьер краснил ВЕРНЫЙ вход: короткий ответ «принято,
        # цепочка закрыта» не содержит ни одного числа, а требование набора
        # numbers делало его непубликуемым. Проверка обязана ловить «числа в
        # тексте без объявленного набора», а не отсутствие чисел вообще:
        # проверка, падающая на верном входе, хуже отсутствующей — ей начинают
        # не верить и обходят её целиком.
        draft_has_numbers = False
        for _p in a.draft:
            try:
                _t = open(_p, encoding='utf-8').read()
            except OSError:
                continue
            if any(numbers_in_groups(_t)):
                draft_has_numbers = True
                break
        if draft_has_numbers:
            fails.append('НЕТ ЧИСЕЛ В FACTS: в черновике есть числа, а numbers пуст — сверять не с чем.')
        else:
            warns.append('числовых утверждений в черновике нет — набор numbers не требуется')
    for path in a.draft:
        text = open(path, encoding='utf-8').read()
        # Дыра, найденная тестом tests/test_publish_gate.py: пустой черновик
        # проходил шлюз с OPEN. Публиковать нечего — значит это отказ, а не PASS.
        if not text.strip():
            fails.append('%s: ПУСТОЙ ЧЕРНОВИК — публиковать нечего, это отказ, '
                         'а не прохождение.' % path)
            continue
        unknown = []
        for group in numbers_in_groups(text):
            # Группа — варианты записи одного числа (12 345 / 12345 / 1.234).
            # Известным считаем число, если совпал ХОТЬ ОДИН вариант: иначе
            # запись «111.30» падала на вариант «11130», которого в тексте нет.
            hit = False
            for n in group:
                if n in known_forms:
                    hit = True; break
                try:
                    if float(n) in known_vals:
                        hit = True; break
                except ValueError:
                    pass
            if not hit:
                unknown.append(sorted(group, key=len)[0])
        # Число, которого нет в прогоне, — это ровно та ошибка, из-за которой
        # «63,6 %» вместо «75 %» ушло в публикацию. Поэтому FAIL, а не заметка.
        if unknown:
            fails.append('%s: ЧИСЛА ВНЕ ПРОГОНА — их нет в facts.numbers, значит взяты не из замера: %s'
                         % (path, ', '.join(unknown[:40])))

    print('=' * 62)
    print('ПРОВЕРКА ВЫВОДА ПЕРЕД ПУБЛИКАЦИЕЙ')
    print('источник: %s | окно: %s' % (f.get('source', '—'), f.get('window', '—')))
    print('знаменатель: %s' % json.dumps(den, ensure_ascii=False))
    print('контроль: %s' % json.dumps(ctl, ensure_ascii=False))
    print('альтернатива: %s' % json.dumps(alt, ensure_ascii=False))
    print('-' * 62)
    for w in warns:
        print('⚠  ' + w)
    for e in fails:
        print('✗  ' + e)
    if fails:
        print('-' * 62)
        print('РЕЗУЛЬТАТ: FAIL — публиковать нельзя, пока не закрыты пункты выше.')
        return 1
    print('-' * 62)
    print('РЕЗУЛЬТАТ: PASS — обязательные проверки пройдены%s.' % (' (числа сверить руками)' if warns else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
