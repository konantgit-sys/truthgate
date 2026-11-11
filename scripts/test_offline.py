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

# Фикстуры: если в репозитории их нет (board/replies/* — рабочие черновики, их
# наружу не выкладывают), собираем свои во временном каталоге. До 11.11.2026 тест
# в этом случае молча писал «нет входных файлов» и не проверял барьер вообще — то
# есть внешний проверяющий не мог им ничего доказать (находка cross-agent-fieldnotes,
# seq 117383: в опубликованном дереве не хватало путей).
FACTS = os.path.join(DASH, 'board', 'replies', 'ans_final17_73511.facts.json')
DRAFT = os.path.join(DASH, 'board', 'replies', 'ans_final17_73511.md')

FIXTURE_FACTS = {
    "denominator": {"проверяемых строк": 3},
    "control": {"объект": "версия контракта борды",
                "live": {"url": "https://getpostingboard.dev/openapi.json",
                         "path": "info.version", "expect": "fixture-offline",
                         "auth": "none"},
                "значение": "fixture-offline", "проверено": True},
    "numbers": [3, 1, 17],
    "alternative": {"гипотеза": "страница пуста, потому что данных нет",
                    "опровергает": "страница пуста, потому что запрос не прошёл"},
    "source": "test_offline: согласованные выдуманные данные",
    "window": "25.09.2026",
}
FIXTURE_DRAFT = 'Верный черновик: три строки, из них одна проверена.'


def ensure_inputs():
    """Возвращает (facts, draft); при отсутствии репозиторных — синтетические."""
    if os.path.exists(FACTS) and os.path.exists(DRAFT):
        return FACTS, DRAFT, 'репозиторные'
    import tempfile
    d = tempfile.mkdtemp(prefix='gate-fixtures-')
    f = os.path.join(d, 'fixture.facts.json')
    t = os.path.join(d, 'fixture.md')
    with io.open(f, 'w', encoding='utf-8') as fh:
        json.dump(FIXTURE_FACTS, fh, ensure_ascii=False)
    with io.open(t, 'w', encoding='utf-8') as fh:
        fh.write(FIXTURE_DRAFT + '\n')
    return f, t, 'синтетические (временный каталог)'

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


def run_gate(offline, facts_path=None, draft_path=None):
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
    ) % (HERE, facts_path or FACTS, draft_path or DRAFT,
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


# --- 11.11.2026: самотест ОБОЛОЧКИ (gate_selftest.sh), а не только verify_claim ---
# Повод: cross-agent-fieldnotes (seq 118451) прочитал код и показал, что
# GATE_SELFTEST_OFFLINE=1 всё равно ходил в сеть за info.version. Сетевой
# перехват в этом же процессе не видит сеть, сделанную дочерним python3 из bash,
# поэтому ловим иначе: подсовываем заведомо мёртвый прокси и смотрим, пытался
# ли скрипт вообще: строка «не получена» появляется только после попытки.

SELFTEST = os.path.join(DASH, 'scripts', 'gate_selftest.sh')
DEAD_PROXY = 'http://127.0.0.1:9'


def _run_selftest(env_extra):
    env = dict(os.environ)
    env.update({
        'http_proxy': DEAD_PROXY, 'https_proxy': DEAD_PROXY, 'all_proxy': DEAD_PROXY,
        'HTTP_PROXY': DEAD_PROXY, 'HTTPS_PROXY': DEAD_PROXY, 'ALL_PROXY': DEAD_PROXY,
        'no_proxy': '', 'NO_PROXY': '',
    })
    env.update(env_extra or {})
    p = subprocess.run(['bash', SELFTEST], capture_output=True, text=True, cwd=DASH, env=env, timeout=180)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def check_selftest_offline():
    """Офлайн-прогон оболочки: ноль попыток в сеть, и тест при этом не слепой."""
    ok, problems = 0, []
    if not os.path.exists(SELFTEST):
        return 0, ['нет %s' % SELFTEST]
    rc, out = _run_selftest({'GATE_SELFTEST_OFFLINE': '1'})
    if 'живая версия контракта не получена' in out:
        problems.append('с GATE_SELFTEST_OFFLINE=1 оболочка всё равно ходила в сеть за info.version')
    elif 'offline: живая версия контракта не запрашивается' in out:
        ok += 1
    else:
        problems.append('офлайн-прогон оболочки не сказал, что сеть не запрашивается')
    if rc == 0:
        ok += 1
    else:
        problems.append('офлайн-прогон оболочки вернул код %s' % rc)
    # слепота: без флага (но с мёртвым прокси) попытка обязана быть видна
    rc2, out2 = _run_selftest({})
    if 'живая версия контракта не получена' in out2:
        ok += 1
    else:
        problems.append('без флага попытка сети не видна — тест слепой, режимы не различимы')
    return ok, problems


def _real_run_restore():
    # Вернуть настоящий subprocess.run: тест сам запускает процессы.
    pass


def main():
    # 11.11.2026: самопроверка оболочки не зависит от фикстур verify_claim и
    # выполняется всегда — иначе тест молча пропускал ровно тот дефект, который
    # нашёл внешний проверяющий.
    s_ok, s_problems = check_selftest_offline()
    f_path, d_path, origin = ensure_inputs()
    print('САМОТЕСТ ОФЛАЙНА: входы — %s' % origin)
    print('САМОТЕСТ ОФЛАЙНА: оболочка — успешно %d, провалов %d' % (s_ok, len(s_problems)))
    facts = json.load(io.open(f_path, encoding='utf-8'))
    has_live = bool((facts.get('control') or {}).get('live'))
    if not has_live:
        print('САМОТЕСТ ОФЛАЙНА: во входе нет control.live — тест не отличит режимы, нужен другой вход')
        return 1

    ok = s_ok
    problems = list(s_problems)

    out_off, net_off = run_gate(True, f_path, d_path)
    if net_off == 0:
        ok += 1
    else:
        problems.append('офлайн-прогон лез в сеть: попыток %s (%s)' % (net_off, out_off[-200:]))
    if 'PASS БЕЗ LIVE' in out_off:
        ok += 1
    else:
        problems.append('офлайн-прогон не сказал, что live-контроль не исполнялся')

    out_on, net_on = run_gate(False, f_path, d_path)
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
