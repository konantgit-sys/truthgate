#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Один барьер — одна копия кода. Синхронизация и проверка копий.

Повод (04.10.2026). Проверял другое и наткнулся: барьер публикации существует
в трёх файлах — в tools/truthgate (рабочий), в sites/gpb-dash/scripts и в
staging/public-ledger-accountability/scripts. Копии разъехались: 80 и 62 строки
различий. В публичной копии не было двух починок, которые есть в рабочей, —
обезличивания нашей подписи в числах (19.09) и хождения по спискам в контроле
(24.09). То есть внешний проверяющий, взяв публичный барьер, получил бы БОЛЕЕ
СЛАБУЮ проверку, чем та, которой мы пользуемся сами, и «проверить без доверия
ко мне» стало бы обещанием без покрытия: он проверил бы другим барьером и
получил бы другой результат.

Как устроено: эталон — tools/truthgate/verify_claim.py. Производные копии
собираются ИЗ НЕГО заменой ровно двух вещей:
  1) блок в docstring с внутренними путями → нейтральный текст;
  2) путь к ключу борды → пустая строка, ключ берётся только из переменной
     окружения GATE_BOARD_KEY_FILE (в публичном контуре нашего ключа нет и
     быть не должно).
Всё остальное обязано совпадать посимвольно. Любая другая правка, сделанная
в производной копии руками, будет затёрта при следующей синхронизации — это
нарочно: у барьера должен быть один источник, иначе это снова три барьера.

Запуск:
  python3 scripts/sync_gate_copies.py            # синхронизировать производные
  python3 scripts/sync_gate_copies.py --check    # только проверить (для монитора)
Код возврата: 0 — копии совпадают (или успешно синхронизированы); 1 — расхождение.
"""
import argparse
import re
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# Пути задаются переменными окружения: публичная копия не описывает раскладку
# рабочего каталога. По умолчанию берём текущее дерево и его соседей.
ROOT = os.path.dirname(HERE)
DASH = os.environ.get('PUB_SYNC_DASH', os.path.join(os.path.dirname(ROOT), 'sites', 'gpb-dash'))
TOOLS = os.environ.get('PUB_SYNC_TOOLS', os.path.join(os.path.dirname(ROOT), 'tools', 'truthgate'))
PUBLIC = os.environ.get('PUB_SYNC_PUBLIC', ROOT)

SRC = os.path.join(TOOLS, 'verify_claim.py')

DERIVED = [
    os.path.join(DASH, 'scripts', 'verify_claim.py'),
    os.path.join(PUBLIC, 'scripts', 'verify_claim.py'),
]

KEY_PATH = "'<путь к файлу ключа задаётся переменной окружения>'"

DOC_BLOCK = """Общий модуль (не бордовый). Лежит в общем дереве инструментов и
вызывается из любого проекта: борда, Cryter, DesignForge, SNIN, отчёты.
Бордовая обёртка — sites/gpb-dash/scripts/publish_gate.sh (обратная совместимость).
Ключ борды нужен только для контроля с auth='board'; файл задаётся переменной
GATE_BOARD_KEY_FILE, по умолчанию — прежний путь. Без auth='board' модуль
работает полностью автономно."""

DOC_REPLACEMENT = """Этот файл — копия рабочего барьера, собранная из эталона
скриптом scripts/sync_gate_copies.py. Барьер обязан быть один: копии, которые
правят руками, расходятся и дают разные ответы на один и тот же черновик.
Ключ борды нужен только для контроля с auth='board' и задаётся переменной
окружения GATE_BOARD_KEY_FILE; без auth='board' модуль работает автономно."""


def build(src_text):
    t = src_text
    DOC_RE = re.compile(r'Общий модуль \(не бордовый\)\..*?работает полностью автономно\.', re.S)
    if not DOC_RE.search(t):
        raise SystemExit('sync_gate_copies: не найден блок docstring для замены — '
                         'эталон изменился, скрипт надо поправить вместе с ним')
    # 18.10.2026: сверка по регулярке, а не по точной строке. Эталон получил новый
    # путь узла в первой строке блока, точная строка перестала совпадать, и скрипт
    # отказывался синхронизировать: производные копии оставались старыми, а тест
    # гонял именно их. Замена — весь блок «Общий модуль … автономно.» целиком.
    t = DOC_RE.sub(DOC_REPLACEMENT, t, count=1)
    # Путь к нашему ключу не должен уезжать в производные копии.
    # 04.10.2026: сверка по точной строке ломалась от сдвига отступа (эталон
    # получил новую ветку и путь уехал на четыре пробела глубже) — скрипт
    # отказывался синхронизировать, производная копия оставалась старой,
    # а самотест при этом гонял именно её. Теперь сверка по образцу строки,
    # а не по её точному тексту с отступами.
    # 18.10.2026: сверка по образцу, а не по заглушке. В эталоне путь записан
    # реальной строкой и разбит переносом — прежняя подстановка его не находила,
    # и реальный путь узла уезжал в публичную копию. Теперь: replace любой
    # строки в этом аргументе, затем жёсткая проверка на остаток.
    t = re.sub(r"kf = os\.environ\.get\('GATE_BOARD_KEY_FILE',\s*'[^']*'\s*\)",
               "kf = os.environ.get('GATE_BOARD_KEY_FILE', '')", t)
    for leak in ('/home/agent', '.secure', 'getpostingboard_key'):
        if leak in t:
            raise SystemExit('sync_gate_copies: в производной копии осталось %r — '
                             'утечка раскладки/ключа, публиковать нельзя' % leak)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='только проверить, не писать')
    a = ap.parse_args()

    src = open(SRC, encoding='utf-8').read()
    want = build(src)
    bad = []
    for path in DERIVED:
        # 18.10.2026: производная копия импортирует reasons (словарь кодов отказа)
        # из СВОЕГО каталога. Без этого файла импорт падал, verify_claim молча
        # откатывался на код 1, и самопроверка барьера видела «все причины = 1»
        # при зелёном тесте — ровно тот дефект, который коды и должны были убрать.
        rs = os.path.join(os.path.dirname(path), 'reasons.py')
        want_r = open(os.path.join(TOOLS, 'reasons.py'), encoding='utf-8').read()
        cur_r = open(rs, encoding='utf-8').read() if os.path.exists(rs) else ''
        if cur_r != want_r:
            if a.check:
                bad.append(rs)
                print(f'РАСХОЖДЕНИЕ {rs} — словарь кодов не совпадает с эталоном')
            else:
                with open(rs, 'w', encoding='utf-8') as f:
                    f.write(want_r)
                print(f'СИНХРОНИЗИРОВАНО {rs}')
        cur = open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        if cur == want:
            print(f'OK    {path} — совпадает с эталоном')
            continue
        if a.check:
            bad.append(path)
            print(f'РАСХОЖДЕНИЕ {path} — {len(cur.splitlines())} против {len(want.splitlines())} строк')
        else:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(want)
            print(f'СИНХРОНИЗИРОВАНО {path}')

    if a.check and bad:
        print('ВЕРДИКТ: FAIL — у барьера несколько версий; внешняя проверка слабее нашей')
        return 1
    print('ВЕРДИКТ: PASS — ' + ('копии совпадают с эталоном' if a.check else 'производные собраны из эталона'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
