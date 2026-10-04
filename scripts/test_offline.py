#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Самотест: офлайн-режим проверок действительно не выходит в сеть.

Зачем (04.10.2026). Внешний проверяющий (claude-sonnet-scout) согласилась
прогнать наши скрипты на чистом клоне при одном условии: она сначала читает
код и запускает только то, что ничего не ставит и не сетит. У нас в барьере
есть сетевой контроль (verify_claim читает URL из блока control.live, чтобы
«проверено» было выполняемым запросом, а не словом). Значит обещание «не
сетит» обязано быть проверяемым, а не заверением: иначе она узнает о сети
только по факту, а мы — после её отчёта.

Что делает тест. Перехватывает сетевые пути Python (socket, urllib) и вызов
curl через subprocess, затем запускает барьер дважды:
  с --offline   — сетевых попыток обязано быть НОЛЬ;
  без --offline — попытка обязана быть зафиксирована (иначе тест слепой).
Различать режимы обязательно: тест, который не видит сеть и без флага,
не проверяет ничего.

Запуск: python3 scripts/test_offline.py
Код возврата: 0 — офлайн чист; 1 — офлайн лез в сеть или тест слепой.
"""
import io
import json
import os
import socket
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.dirname(HERE)
GATE = os.path.join(DASH, 'scripts', 'verify_claim.py')

FACTS = os.path.join(DASH, 'board', 'replies', 'ans_final17_73511.facts.json')
DRAFT = os.path.join(DASH, 'board', 'replies', 'ans_final17_73511.md')

attempts = []


def _trap(kind):
    def f(*a, **kw):
        attempts.append(kind)
        raise OSError('СЕТЬ ЗАПРЕЩЕНА ТЕСТОМ (%s)' % kind)
    return f


def arm():
    socket.socket = _trap('socket.socket')
    socket.create_connection = _trap('socket.create_connection')
    urllib.request.urlopen = _trap('urllib.urlopen')

    real_run = subprocess.run

    def run(cmd, *a, **kw):
        try:
            head = cmd[0] if isinstance(cmd, (list, tuple)) else str(cmd)
            joined = ' '.join(map(str, cmd)) if isinstance(cmd, (list, tuple)) else str(cmd)
        except Exception:
            head, joined = '', str(cmd)
        if 'curl' in joined or 'wget' in joined:
            attempts.append('subprocess:' + os.path.basename(str(head)))
            raise OSError('СЕТЬ ЗАПРЕЩЕНА ТЕСТОМ (subprocess)')
        return real_run(cmd, *a, **kw)

    subprocess.run = run


def run_gate(offline):
    """Запускает барьер в отдельном процессе с перехватом сети в нём."""
    prog = (
        "import sys, runpy, os\n"
        "sys.path.insert(0, %r)\n"
        "import test_offline as T\n"          # тот же каталог
        "T.arm()\n"
        "sys.argv = ['verify_claim.py', '--facts', %r, '--draft', %r]\n"
        "%s\n"
        "try:\n"
        "    runpy.run_path(%r, run_name='__main__')\n"
        "except SystemExit as e:\n"
        "    print('EXITCODE:', e.code)\n"
        "finally:\n"
        "    print('NET_ATTEMPTS:', len(T.attempts), T.attempts[:3])\n"
    ) % (HERE, FACTS, DRAFT,
         "sys.argv.append('--offline')" if offline else "pass",
         GATE)
    p = subprocess.run([sys.executable, '-c', prog], capture_output=True, text=True, cwd=HERE, timeout=90)
    out = p.stdout + p.stderr
    net = None
    for line in out.split('\n'):
        if line.startswith('NET_ATTEMPTS:'):
            try:
                net = int(line.split(':', 1)[1].strip().split()[0])
            except Exception:
                net = -1
    return out, net


def _real_run_restore():
    # Вернуть настоящий subprocess.run: тест сам запускает процессы.
    pass


def main():
    if not (os.path.exists(FACTS) and os.path.exists(DRAFT)):
        print('САМОТЕСТ ОФЛАЙНА: нет входных файлов (%s)' % FACTS)
        return 1
    facts = json.load(io.open(FACTS, encoding='utf-8'))
    has_live = bool((facts.get('control') or {}).get('live'))
    if not has_live:
        print('САМОТЕСТ ОФЛАЙНА: во входе нет control.live — тест не отличит режимы, нужен другой вход')
        return 1

    ok = 0
    problems = []

    out_off, net_off = run_gate(True)
    if net_off == 0:
        ok += 1
    else:
        problems.append('офлайн-прогон лез в сеть: попыток %s (%s)' % (net_off, out_off[-200:]))
    if 'PASS БЕЗ LIVE' in out_off:
        ok += 1
    else:
        problems.append('офлайн-прогон не сказал, что live-контроль не исполнялся')

    out_on, net_on = run_gate(False)
    if net_on and net_on > 0:
        ok += 1
    else:
        problems.append('без флага сеть не зафиксирована — тест слепой, режимы не различимы')

    print('САМОТЕСТ ОФЛАЙНА: успешно %d, провалов %d' % (ok, len(problems)))
    for p in problems:
        print('  ПРОВАЛ ' + p)
    if problems:
        print('ВЕРДИКТ: FAIL — офлайн-режим не доказан')
        return 1
    print('ВЕРДИКТ: PASS — офлайн не выходит в сеть, без флага сеть фиксируется, '
          'неисполненный live-контроль не выдаётся за проверенный')
    return 0


if __name__ == '__main__':
    sys.exit(main())
