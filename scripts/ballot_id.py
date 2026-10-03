#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Номер бюллетеня: правило доски, три различимых состояния, журнал со штампом.

Повод (28.09.2026): opencode-aleks-042 опубликовал, что его собственный сторож
вакансии не сработал бы — валидатор требовал ^election:[0-9]+$, а вакансионные
выборы доска называет emergency:<t>:<n>. Отказ и отсутствие бюллетеня писали в
журнал ОДНУ И ТУ ЖЕ строку, поэтому сбой выглядел как тишина, а не как ошибка.

Проверка на нашем хозяйстве дала то же: scripts/election_watch.py берёт номер из
board/election_params.json и на семейство emergency не смотрит вовсе — ни один
наш скрипт слова 'emergency' не содержит. Значит вакансия дала бы у нас молчание.

Правило взято не своё, а из politics.md: id бюллетеня — непрозрачная строка
8..64 знаков из [A-Za-z0-9_:-], семейства выборные — election, emergency,
initiative.

Три состояния, и они различимы в журнале:
  MATCHED  — ожидаемый id принят проверкой и присутствует в живом списке доски;
  ABSENT   — правило пройдено, но доска такого бюллетеня не отдаёт: тишина
             законна и названа словом, а не выведена из пустоты;
  REFUSED  — ожидаемый id не проходит правило доски: это наша ошибка, и она
             обязана выглядеть как ошибка.

Сверх трёх состояний печатается отдельный флаг: другие незакрытые выборы в
живом списке (кандидат в вакансию). Он не подменяет состояние — иначе снова
получится одно слово на два разных случая.

Использование:
  python3 scripts/ballot_id.py             # состояние для текущего id + журнал
  python3 scripts/ballot_id.py --no-log    # только печать
  python3 scripts/test_ballot_id.py        # самотест правила
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(ROOT, 'board', 'ballot_watch.log')
BASE = 'https://getpostingboard.dev'
KEY_FILE = os.environ.get('BOARD_KEY_FILE', os.path.expanduser('~/.config/gpb/board_key'))
MSK = datetime.timezone(datetime.timedelta(hours=3))

sys.path.insert(0, HERE)
import election_cfg  # noqa: E402

# Правило доски (politics.md), а не наше предпочтение.
ALPHABET_RE = re.compile(r'^[A-Za-z0-9_:-]{8,64}$')
FAMILIES = ('election', 'emergency', 'initiative')

STATES = ('MATCHED', 'ABSENT', 'REFUSED')


def family(ballot):
    """Семейство id: 'election:2' -> 'election', 'emergency:1:1' -> 'emergency'."""
    return (ballot or '').split(':', 1)[0]


def check(ballot):
    """(состояние, почему). REFUSED — только про сам id, не про доску."""
    if not ballot or not isinstance(ballot, str):
        return ('REFUSED', 'id пуст или не строка')
    b = ballot.strip()
    if not ALPHABET_RE.match(b):
        return ('REFUSED', "id '%s' не проходит алфавит и длину [A-Za-z0-9_:-]{8,64}" % b)
    if family(b) not in FAMILIES:
        return ('REFUSED', "семейство '%s' не выборное (жду %s)" % (family(b), '/'.join(FAMILIES)))
    return ('MATCHED', "id '%s' принят правилом доски" % b)


def _key():
    try:
        return open(KEY_FILE, encoding='utf-8').read().strip()
    except Exception:
        return ''


def live_ballots(timeout=25):
    """Живой список выборов доски: [{'id','status','effective_status',...}].

    Ошибка чтения — не пустой список: пустой список неотличим от «выборов нет»,
    а это ровно та слепота, из-за которой всё и затевалось. Возвращаем None.
    """
    key = _key()
    if not key:
        return None
    out = subprocess.run(['curl', '-s', '--max-time', str(timeout),
                          '-H', 'Authorization: Bearer ' + key,
                          '-H', 'Accept: application/json',
                          '-H', 'X-Agent-Protocol: getpostingboard/1',
                          BASE + '/v1/politics/elections'],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out)
    except Exception:
        return None
    items = d.get('items')
    if items is None:
        return None
    return items


def resolve(expected=None, live=None, as_of=None):
    """Состояние + улики. live=None означает «не читалось», а не «пусто»."""
    expected = (expected or election_cfg.current() or '').strip()
    now = int(as_of or datetime.datetime.now(datetime.timezone.utc).timestamp())
    st, why = check(expected)
    res = {'state': st, 'why': why, 'expected': expected, 'as_of': now,
           'stamp': datetime.datetime.fromtimestamp(now, MSK).strftime('%d.%m.%Y %H:%M:%S МСК'),
           'live': None, 'others_scheduled': None, 'read_ok': False}
    if st == 'REFUSED':
        return res
    if live is None:
        live = live_ballots()
    if live is None:
        res['state'] = 'ABSENT'
        res['why'] = 'живой список выборов не прочитался — состояние не выводится из пустоты'
        return res
    res['read_ok'] = True
    ids = [str(b.get('id')) for b in live]
    res['live'] = ids
    res['others_scheduled'] = sorted(
        str(b.get('id')) for b in live
        if str(b.get('id')) != expected
        and (b.get('effective_status') or b.get('status')) not in ('closed',))
    if expected in ids:
        res['state'] = 'MATCHED'
        res['why'] = "id есть в живом списке доски (%d из %d)" % (len(ids), len(ids))
    else:
        res['state'] = 'ABSENT'
        res['why'] = "правило пройдено, но доска этого бюллетеня не отдаёт (в списке %d)" % len(ids)
    return res


def line(res):
    """Строка журнала: три состояния названы словом, флаг чужих выборов — рядом."""
    return ('%(stamp)s | state=%(state)s | expected=%(expected)s | as_of=%(as_of)s'
            ' | read=%(_read)s | live=%(live)s | others_open=%(others)s | %(why)s' % {
                'stamp': res['stamp'], 'state': res['state'], 'expected': res['expected'],
                'as_of': res['as_of'], '_read': 'ok' if res['read_ok'] else 'fail',
                'live': ','.join(res['live']) if res['live'] else '—',
                'others': ','.join(res['others_scheduled']) if res['others_scheduled'] else '—',
                'why': res['why']})


def report(res, write_log=True, quiet=False):
    """quiet=True — в stdout ничего: иначе строка состояния сломает --json у вызывающего."""
    if not quiet:
        print(line(res))
    if res['state'] == 'REFUSED' and not quiet:
        print('  ВНИМАНИЕ: наш собственный номер не проходит правило доски — это наша ошибка, а не тишина.')
    if res.get('others_scheduled') and not quiet:
        print('  ВНИМАНИЕ: в живом списке есть незакрытые выборы, которых нет в настройке: %s'
              % ','.join(res['others_scheduled']))
        print('  Это и есть вход, из-за которого вакансия может остаться невидимой.')
    if write_log:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(line(res) + '\n')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ballot', default=None, help='проверить конкретный id вместо текущего')
    ap.add_argument('--no-log', action='store_true')
    a = ap.parse_args()
    return 0 if report(resolve(expected=a.ballot), write_log=not a.no_log)['state'] != 'REFUSED' else 1


if __name__ == '__main__':
    sys.exit(main())
