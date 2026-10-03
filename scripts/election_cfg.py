#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Какие выборы считать текущими — одно место вместо литерала election:1.

Повод: 26.09.2026 найдено, что вся выборная обвязка прибита к election:1, а
election:2 открывается 30.09 в 03:00 МСК. Двадцать два файла держали строку
'election:1' в коде; кроны стояли на дату 23.09. После закрытия election:1 это
значило тишину: наблюдатель смотрел бы в закрытый бюллетень, снимок открытия не
снялся бы, карточка результата считала бы прошлые выборы.

Правило: номер выборов берётся отсюда, файл board/election_params.json можно
править без правки кода. Ошибка чтения — не повод молчать: возвращаем значение
из DEFAULT, а не пустую строку.

Проверка: scripts/test_election_cfg.py (значение, границы дат, статический
контроль, что cron-скрипты не держат литерал election:1 в присваивании).
"""
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, '..', 'board', 'election_params.json')

DEFAULT = 'election:2'


def _load():
    try:
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def current():
    """Номер текущих выборов, например 'election:2'."""
    value = (_load().get('current_election') or '').strip()
    return value or DEFAULT


def previous():
    return (_load().get('previous_election') or 'election:1').strip()


def param(name, default=None):
    return _load().get(name, default)


def opens_at_utc():
    return _load().get('opens_at_utc')


def closes_at_utc():
    return _load().get('closes_at_utc')


def opens_at_msk():
    """Открытие окна словами, как в board/election_params.json (30.09.2026 03:00)."""
    return _load().get('opens_at_msk')


def closes_at_msk():
    return _load().get('closes_at_msk')


def closes_ts():
    """Время закрытия текущих выборов в epoch UTC. 0, если дата не разбирается.

    Зачем: night_daemon держал закрытие литералом 17.09 (election:1), поэтому
    окно публикации итога для второго созыва не открылось ни разу.
    """
    try:
        dt = datetime.datetime.strptime(closes_at_utc(), '%Y-%m-%dT%H:%M:%SZ')
        return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp())
    except Exception:
        return 0


def published_key(eid=None):
    """Ключ состояния «итог этого созыва опубликован» — своё имя на каждый созыв.

    Прежний общий ключ election_publish_seq остаётся в файле как история, но
    отметка одного созыва больше не закрывает публикацию следующего.
    """
    return 'election_publish_seq:%s' % (eid or current())


def result_published(state, eid=None):
    """Опубликован ли итог этих выборов. Флаг прошлого созыва не в счёт."""
    if not isinstance(state, dict):
        return False
    if state.get(published_key(eid)) is not None:
        return True
    # совместимость: у прошлых выборов отметка лежала в общем ключе
    if (eid or current()) == previous():
        return state.get('election_publish_seq') is not None
    return False


def mark_published(state, seq, eid=None):
    """Отметить итог опубликованным; возвращает (state, ключ)."""
    k = published_key(eid)
    state[k] = seq
    return state, k


# то, что импортируют скрипты
ELECTION = current()


if __name__ == '__main__':
    print('текущие выборы: %s' % ELECTION)
    print('предыдущие:     %s' % previous())
    print('открытие:       %s (%s)' % (opens_at_utc(), param('opens_at_msk')))
    print('закрытие:       %s (%s)' % (closes_at_utc(), param('closes_at_msk')))
    print('кворум:         %s | подсчёт: %s' % (param('quorum_min'), param('counting')))
