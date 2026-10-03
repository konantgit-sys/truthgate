#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Самотест правила id бюллетеня и трёх состояний. Без сети: живой список подменяем.

Смысл набора — не «функция возвращает строку», а: (а) вакансионный id
emergency:1:1 принимается (именно на нём сломался сторож aleks),
(б) мусорные id отбиваются, (в) непрочитанный список НЕ выглядит как
«выборов нет», (г) чужая незакрытая вакансия видна отдельным флагом даже
когда наш бюллетень отсутствует.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ballot_id as B  # noqa: E402

FAILS = []
N = 0


def ok(name, cond, extra=''):
    global N
    N += 1
    if cond:
        print('  PASS  %s' % name)
    else:
        print('  FAIL  %s %s' % (name, extra))
        FAILS.append(name)


CLOSED = {'id': 'election:1', 'status': 'closed', 'effective_status': 'closed'}
SCHED = {'id': 'election:2', 'status': 'scheduled', 'effective_status': 'scheduled'}
VAC = {'id': 'emergency:1:1', 'status': 'scheduled', 'effective_status': 'scheduled'}

print('правило id (алфавит и семейство):')
ok('election:2 принят', B.check('election:2')[0] == 'MATCHED')
ok('emergency:1:1 принят — тот самый случай', B.check('emergency:1:1')[0] == 'MATCHED',
   B.check('emergency:1:1')[1])
ok('initiative:3 принят', B.check('initiative:3')[0] == 'MATCHED')
ok('e3 отбит (короткий)', B.check('e3')[0] == 'REFUSED')
ok('emergency:1:1/../x отбит (чужие знаки)', B.check('emergency:1:1/../x')[0] == 'REFUSED')
ok('пустой id отбит', B.check('')[0] == 'REFUSED')
ok('banana:1:1 отбит (не выборное семейство)', B.check('banana:1:1')[0] == 'REFUSED')
ok('слишком длинный id отбит', B.check('election:' + 'a' * 70)[0] == 'REFUSED')

print('три состояния:')
r = B.resolve(expected='election:2', live=[CLOSED, SCHED], as_of=1)
ok('MATCHED, когда id есть в списке', r['state'] == 'MATCHED', r['state'])
ok('MATCHED не поднимает флаг на закрытый чужой бюллетень', r['others_scheduled'] == [],
   str(r['others_scheduled']))

r = B.resolve(expected='election:2', live=[CLOSED], as_of=1)
ok('ABSENT, когда правила прошли, а бюллетеня нет', r['state'] == 'ABSENT', r['state'])

r = B.resolve(expected='e3', live=[SCHED], as_of=1)
ok('REFUSED, когда отбит наш собственный id', r['state'] == 'REFUSED', r['state'])
ok('REFUSED не делает вида, что список читался', r['read_ok'] is False)

_saved = B.live_ballots
B.live_ballots = lambda timeout=25: None
r = B.resolve(expected='election:2', as_of=1)
B.live_ballots = _saved
ok('непрочитанный список даёт ABSENT, а не «выборов нет»',
   r['state'] == 'ABSENT' and r['read_ok'] is False, '%s read_ok=%s' % (r['state'], r['read_ok']))

print('вакансия не должна быть невидимой:')
r = B.resolve(expected='election:2', live=[CLOSED, VAC], as_of=1)
ok('наш бюллетень отсутствует -> ABSENT', r['state'] == 'ABSENT', r['state'])
ok('вакансия поднята флагом others_open', r['others_scheduled'] == ['emergency:1:1'],
   str(r['others_scheduled']))
ok('в строке журнала есть и состояние, и штамп, и флаг',
   'state=ABSENT' in B.line(r) and 'as_of=1' in B.line(r) and 'others_open=emergency:1:1' in B.line(r))

print()
print('ИТОГ: %d проверок, провалов %d' % (N, len(FAILS)))
if FAILS:
    print('провалено: %s' % ', '.join(FAILS))
sys.exit(1 if FAILS else 0)
