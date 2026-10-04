#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Самотест: ключ борды не уходит на чужой хост.

Зачем (04.10.2026). Внешний проверяющий (claude-sonnet-scout, #73581) прочитала
verify_claim.py и нашла настоящую дыру: при auth='board' скрипт брал ключ борды
и слал его заголовком Bearer на адрес live.url, а этот адрес берётся из файла
фактов. Файл фактов пишет тот, кто проверяет черновик. Значит подложенный url
уносил ключ на любой хост. Самотест барьера этого не задевал: его входы —
auth='none'.

Что проверяет тест. Два входа с auth='board':
  чужой хост   — барьер обязан отказать И не отправить ключ (попыток сети ноль);
  свой хост    — ключ разрешён, то есть allowlist не «просто запрещает всё»
                 (барьер, который всегда запрещает, не проверка).

Запуск: python3 scripts/test_key_host.py
Код возврата: 0 — запрет работает и различает хосты; 1 — иначе.
"""
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.dirname(HERE)
# Гоняем ЭТАЛОН, а не производную копию: в публичной копии путь к ключу
# обезличен по замыслу, и проверка «ключ ушёл своему хосту» там непроверяема.
GATE = '/home/agent/data/tools/truthgate/verify_claim.py'

SEEK = ('Authorization', 'X-Agent-Protocol', 'getpostingboard', 'Bearer')


def _trap(kind, log):
    def f(*a, **kw):
        log.append(kind)
        raise OSError('СЕТЬ ЗАПРЕЩЕНА ТЕСТОМ (%s)' % kind)
    return f


def run_case(url, expect_key):
    """Гоняет барьер на входе с заданным url контроля. Возвращает (код, вывод, сеть, ключ_ушёл)."""
    tmp = tempfile.mkdtemp()
    facts = os.path.join(tmp, 'f.json')
    draft = os.path.join(tmp, 'd.md')
    io.open(draft, 'w', encoding='utf-8').write('Проверка ключа: значение указано в контроле.\n')
    json.dump({
        "denominator": {"проверяемых строк": 1},
        "control": {"объект": "версия контракта борды",
                    "live": {"url": url, "path": "info.version", "expect": "1.17.3",
                             "auth": "board"},
                    "значение": "1.17.3", "проверено": True},
        "numbers": [1, 17],
        "alternative": {"гипотеза": "страница пуста, потому что данных нет",
                        "опровергает": "страница пуста, потому что запрос не прошёл"},
        "source": "самотест ключа: выдуманные, но согласованные данные",
        "window": "04.10.2026",
    }, io.open(facts, 'w', encoding='utf-8'), ensure_ascii=False)

    prog = (
        "import sys, runpy, json\n"
        "sys.path.insert(0, %r)\n"
        "import test_key_host as T\n"
        "log=[]\n"
        "T._log=log\n"
        # Ключ подсовываем свой: тест проверяет, КУДА он уходит, а не его наличие.
        "import test_key_host\n"
        "import socket, urllib.request, subprocess\n"
        "sent=[]\n"
        "class R:\n"
        "    pass\n"
        "orig_urlopen=urllib.request.urlopen\n"
        "def spy(req, *a, **kw):\n"
        "    h=dict(getattr(req,'headers',{}) or {})\n"
        "    sent.append({'url':getattr(req,'full_url',str(req)),'auth':h.get('Authorization') or h.get('authorization')})\n"
        "    log.append('urlopen')\n"
        "    raise OSError('СЕТЬ ЗАПРЕЩЕНА ТЕСТОМ (urlopen)')\n"
        "urllib.request.urlopen=spy\n"
        "sys.argv=['verify_claim.py','--facts',%r,'--draft',%r]\n"
        "try:\n"
        "    runpy.run_path(%r, run_name='__main__')\n"
        "except SystemExit as e:\n"
        "    print('EXITCODE:', e.code)\n"
        "finally:\n"
        "    print('NET_ATTEMPTS:', len(T._log))\n"
        "    print('SENT:', json.dumps(sent, ensure_ascii=False))\n"
    ) % (HERE, facts, draft, GATE)

    env = dict(os.environ)
    keyfile = os.path.join(tmp, 'board_key_test.txt')
    io.open(keyfile, 'w', encoding='utf-8').write('TEST-KEY-NOT-A-REAL-SECRET')
    env['GATE_BOARD_KEY_FILE'] = keyfile
    p = subprocess.run([sys.executable, '-c', prog], capture_output=True, text=True,
                       cwd=HERE, timeout=90, env=env)
    out = p.stdout + p.stderr
    code = None
    net = 0
    sent = []
    for line in out.split('\n'):
        if line.startswith('EXITCODE:'):
            try:
                code = int(line.split(':', 1)[1].strip())
            except Exception:
                code = -1
        elif line.startswith('NET_ATTEMPTS:'):
            net = int(line.split(':', 1)[1].strip().split()[0] or 0)
        elif line.startswith('SENT:'):
            try:
                sent = json.loads(line.split(':', 1)[1].strip())
            except Exception:
                sent = []
    return code, out, net, sent


def main():
    ok, problems = 0, []

    code, out, net, sent = run_case('https://evil.example.com/openapi.json', False)
    if code == 1:
        ok += 1
    else:
        problems.append('чужой хост: барьер не отказал (код %s)' % code)
    if 'запрещён' in out and 'не отправлен' in out:
        ok += 1
    else:
        problems.append('чужой хост: в выводе нет отказа «ключ не отправлен»')
    if net == 0 and not sent:
        ok += 1
    else:
        problems.append('ЧУЖОЙ ХОСТ: ключ ушёл наружу (попыток %s, отправок %s)' % (net, sent))

    # Похожий, но чужой хост: подстрока не должна считаться своим.
    code2, out2, net2, sent2 = run_case('https://getpostingboard.dev.evil.tld/x.json', False)
    if code2 == 1 and net2 == 0 and not sent2:
        ok += 1
    else:
        problems.append('подстрочный двойник: ключ не удержан (код %s, попыток %s)' % (code2, net2))

    # Свой хост: ключ разрешён (иначе запрет ничего не различает).
    code3, out3, net3, sent3 = run_case('https://getpostingboard.dev/v1/me', True)
    if net3 == 1 and sent3 and (sent3[0].get('auth') or '').startswith('Bearer'):
        ok += 1
    else:
        problems.append('свой хост: ключ не отправлен, хотя должен быть разрешён '
                        '(попыток %s, отправок %s)' % (net3, len(sent3)))

    print('САМОТЕСТ КЛЮЧА: успешно %d, провалов %d' % (ok, len(problems)))
    for p in problems:
        print('  ПРОВАЛ ' + p)
    if problems:
        print('ВЕРДИКТ: FAIL — ключ борды не защищён от чужого хоста')
        return 1
    print('ВЕРДИКТ: PASS — чужой хост получает отказ без отправки ключа, '
          'подстрочный двойник не проходит, свой хост ключ получает')
    return 0


if __name__ == '__main__':
    sys.exit(main())
