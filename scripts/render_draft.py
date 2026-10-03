#!/usr/bin/env python3
"""Рендер черновика из шаблона: числа в публикуемом тексте не пишутся руками.

ЗАЧЕМ ЭТО ЕСТЬ. Шлюз сверяет числа черновика со списком facts.numbers, но список
неизбежно шире одной фразы: токены времени и дат («12:33», «24.09») приносят в него
12, 24, 33, 39, 40, 53 — и подмена живого числа на другое из того же списка проходит
как PASS. Поймано тестом на дырявом входе 23.09.2026: в письме «21 первых (60.0%)»
заменено на «24 первых (60.0%)», шлюз ответил OPEN. Оговорка «список широкий» —
это и есть дыра, а не оговорка.

КАК ЗАКРЫВАЕТСЯ. Текст письма лежит шаблоном с подстановками вида {{ключ}}, значения
берутся из facts (proc: denominator / structural / text). Барьер собирает текст из
фактов заново и сравнивает с публикуемым файлом посимвольно. Поэтому подмена числа в
файле — это расхождение с рендером, и публикация блокируется. Проверено тестом: та же
подмена 21 → 24 теперь FAIL.

Использование:
  render_draft.py --template tpl/x.tpl.md --facts f.json --write out.md
  render_draft.py --template tpl/x.tpl.md --facts f.json --check out.md

Коды: 0 — ок/совпало; 1 — расхождение или неизвестный ключ; 2 — ошибка вызова.
"""
import argparse
import json
import os
import re
import sys

PLACE = re.compile(r'\{\{([^}]+)\}\}')


def flat(facts):
    out = {}
    for section in ('text', 'structural', 'denominator'):
        d = facts.get(section) or {}
        if isinstance(d, dict):
            for k, v in d.items():
                out.setdefault(k, v)
    return out


def render(tpl, values):
    missing = []

    def sub(m):
        k = m.group(1).strip()
        if k not in values:
            missing.append(k)
            return m.group(0)
        v = values[k]
        s = ('%g' % v) if isinstance(v, float) else str(v)
        return s

    text = PLACE.sub(sub, tpl)
    return text, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--template', required=True)
    ap.add_argument('--facts', required=True)
    ap.add_argument('--write')
    ap.add_argument('--check')
    a = ap.parse_args()
    if not a.write and not a.check:
        print('нужен либо --write, либо --check'); return 2
    try:
        facts = json.load(open(a.facts, encoding='utf-8'))
        tpl = open(a.template, encoding='utf-8').read()
    except Exception as e:
        print('не читается вход: %s' % e); return 2
    text, missing = render(tpl, flat(facts))
    if missing:
        print('НЕИЗВЕСТНЫЕ КЛЮЧИ в шаблоне: %s — публикация без значения недопустима'
              % ', '.join(sorted(set(missing))))
        return 1
    if a.write:
        open(a.write, 'w', encoding='utf-8').write(text)
        print('отрендерено: %s (%d знаков)' % (os.path.basename(a.write), len(text)))
        return 0
    have = open(a.check, encoding='utf-8').read()
    if have == text:
        print('РЕНДЕР СОВПАЛ: %s == %s' % (os.path.basename(a.template), os.path.basename(a.check)))
        return 0
    # показать первое расхождение — иначе барьер молчит, а человек не знает, где искать
    for i, (x, y) in enumerate(zip(have, text)):
        if x != y:
            print('РАСХОЖДЕНИЕ с рендером на знаке %d:' % i)
            print('  в файле: ...%s...' % have[max(0, i - 40):i + 40].replace('\n', ' '))
            print('  в рендере: ...%s...' % text[max(0, i - 40):i + 40].replace('\n', ' '))
            break
    else:
        print('РАСХОЖДЕНИЕ с рендером по длине: в файле %d знаков, в рендере %d'
              % (len(have), len(text)))
    return 1


if __name__ == '__main__':
    sys.exit(main())
