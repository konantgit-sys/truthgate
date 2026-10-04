#!/usr/bin/env python3
"""Заморозка методик на электоральный период: снимок SHA-256 + проверка дрейфа.

Правило (ELECTION FIREWALL, 03.10.2026): в объявленный электоральный период
методика, определения, пороги, фильтры и дашборды заморожены; любое изменение —
только записью в correction ledger. Правило было, механизма не было: «заморожено»
держалось на моей памяти. Здесь механизм.

  method_freeze.py --snapshot            # снять снимок (пишет METHOD_FREEZE.json)
  method_freeze.py --verify              # пересчитать и сравнить; exit 1 при дрейфе
  method_freeze.py --self-test           # тест на дырявом входе: подмена файла обязана быть поймана

exit 0 — PASS (снимок снят или дрейфа нет)
exit 1 — FAIL (дрейф: файл изменён/удалён/добавлен в список методик)
exit 2 — ошибка вызова
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DASH = os.path.dirname(HERE)
DATA = os.path.dirname(os.path.dirname(DASH))
SNAP = os.path.join(DASH, 'board', 'accountability', 'METHOD_FREEZE.json')

# ── что считается методикой (а не данными и не текстом постов) ────────────────
# Файлы перечислены явно, каталоги — масками: добавленный в methodology/ файл
# обязан попасть в снимок, иначе «заморожено» снова станет обещанием.
METHOD_FILES = [
    'sites/gpb-dash/scripts/publish_gate.sh',
    'sites/gpb-dash/scripts/check_time_claims.sh',
    'sites/gpb-dash/scripts/rank_live.py',
    'sites/gpb-dash/scripts/election_watch.py',
    'sites/gpb-dash/scripts/method_freeze.py',
    'sites/gpb-dash/app.py',
    'tools/truthgate/gate.sh',
    'tools/truthgate/verify_claim.py',
    'tools/truthgate/header_check.py',
    'tools/truthgate/mkfacts.py',
    'staging/public-ledger-accountability/README.md',
    'staging/public-ledger-accountability/SCOPE.md',
    'staging/public-ledger-accountability/CONFLICTS.md',
    'staging/public-ledger-accountability/CONTRIBUTING.md',
    'staging/public-ledger-accountability/SHA256SUMS',
    'sites/gpb-dash/board/accountability/ACCOUNTABILITY_CONTRACT_v1.md',
    'sites/gpb-dash/board/accountability/POST_HEADER.md',
    'sites/gpb-dash/board/accountability/VISIBILITY.md',
    'sites/gpb-dash/board/accountability/POSITIONAL_STATEMENT.md',
]
METHOD_GLOBS = [
    'staging/public-ledger-accountability/methodology/*.md',
    'staging/public-ledger-accountability/contracts/*.md',
    'staging/public-ledger-accountability/scripts/*.py',
    'staging/public-ledger-accountability/scripts/*.sh',
    'staging/public-ledger-accountability/scripts/truthgate/*',
]


def method_list(root: str = DATA) -> list[str]:
    import glob as _glob
    rels = list(METHOD_FILES)
    for pattern in METHOD_GLOBS:
        for full in sorted(_glob.glob(os.path.join(root, pattern))):
            rel = os.path.relpath(full, root)
            if rel not in rels and os.path.isfile(full):
                rels.append(rel)
    return rels


def sha256(path: str) -> tuple[str, int]:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(65536), b''):
            h.update(chunk)
    return h.hexdigest(), os.path.getsize(path)


def collect(root: str = DATA) -> dict:
    files, missing = {}, []
    for rel in method_list(root):
        full = os.path.join(root, rel)
        if not os.path.exists(full):
            missing.append(rel)
            continue
        digest, size = sha256(full)
        files[rel] = {'sha256': digest, 'bytes': size}
    root_hash = hashlib.sha256(
        json.dumps({k: v['sha256'] for k, v in sorted(files.items())}, ensure_ascii=False).encode()
    ).hexdigest()
    return {'files': files, 'missing': missing, 'root_hash': root_hash}


def snapshot(election: str = 'election:3') -> int:
    data = collect()
    payload = {
        'frozen_at': int(time.time()),
        'frozen_at_local': time.strftime('%d.%m.%Y %H:%M МСК', time.gmtime(time.time() + 10800)),
        'election': election,
        'rule': 'В электоральный период методика/определения/пороги/фильтры/дашборды не меняются; изменение — только через board/accountability/CORRECTIONS.md.',
        'root_hash': data['root_hash'],
        'files': data['files'],
        'missing': data['missing'],
    }
    os.makedirs(os.path.dirname(SNAP), exist_ok=True)
    with open(SNAP, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print('СНИМОК: %s' % SNAP)
    print('файлов методик: %d | отсутствуют: %d | root_hash: %s' % (len(data['files']), len(data['missing']), data['root_hash'][:16]))
    if data['missing']:
        print('  не найдены: %s' % ', '.join(data['missing']))
    return 0


def verify(quiet: bool = False) -> int:
    if not os.path.exists(SNAP):
        print('НЕТ СНИМКА: сначала --snapshot'); return 2
    frozen = json.load(open(SNAP, encoding='utf-8'))
    now = collect()
    drift = []
    for rel, meta in frozen['files'].items():
        cur = now['files'].get(rel)
        if cur is None:
            drift.append((rel, 'удалён'))
        elif cur['sha256'] != meta['sha256']:
            drift.append((rel, 'изменён: %s → %s' % (meta['sha256'][:12], cur['sha256'][:12])))
    for rel in now['files']:
        if rel not in frozen['files']:
            drift.append((rel, 'появился после снимка'))
    if frozen.get('root_hash') != now['root_hash']:
        drift.append(('root_hash', '%s → %s' % (str(frozen.get('root_hash'))[:12], now['root_hash'][:12])))
    if not drift:
        if not quiet:
            print('ЗАМОРОЗКА: OK — %d файлов методик совпадают со снимком от %s (root %s)'
                  % (len(frozen['files']), frozen.get('frozen_at_local'), str(frozen['root_hash'])[:16]))
        return 0
    print('ЗАМОРОЗКА: ДРЕЙФ — методика менялась после снимка (%d записей):' % len(drift))
    for rel, why in drift:
        print('  ✗ %s — %s' % (rel, why))
    print('Правило: в электоральный период изменение оформляется записью в CORRECTIONS.md, а снимок переснимается вручную.')
    return 1


def self_test() -> int:
    """Тест на дырявом входе: подмена методики обязана ловиться, иначе проверка декоративна."""
    global SNAP
    tmp = tempfile.mkdtemp(prefix='method_freeze_test_')
    real_snap = SNAP
    try:
        # 1) снимок на копии реальных файлов
        SNAP = os.path.join(tmp, 'FREEZE.json')
        data = collect()
        json.dump({'frozen_at': int(time.time()), 'frozen_at_local': 'тест', 'election': 'election:3',
                   'root_hash': data['root_hash'], 'files': data['files'], 'missing': data['missing']},
                  open(SNAP, 'w', encoding='utf-8'), ensure_ascii=False)
        # 2) чистое состояние обязано пройти
        clean = verify(quiet=True)
        # 3) ломаем один методический файл — проверка обязана упасть
        target = os.path.join(DATA, METHOD_FILES[3] if len(METHOD_FILES) > 3 else METHOD_FILES[0])
        backup = target + '.selftest.bak'
        shutil.copy2(target, backup)
        with open(target, 'a', encoding='utf-8') as fh:
            fh.write('\n# подмена методики в тесте\n')
        broken = verify(quiet=True)
        # 4) возвращаем как было и убеждаемся, что снова чисто
        shutil.move(backup, target)
        restored = verify(quiet=True)
    finally:
        SNAP = real_snap
        shutil.rmtree(tmp, ignore_errors=True)

    ok = (clean == 0 and broken == 1 and restored == 0)
    print('  чисто: exit %d (ожидалось 0) %s' % (clean, 'OK' if clean == 0 else 'FAIL'))
    print('  подмена файла методики: exit %d (ожидалось 1) %s' % (broken, 'OK' if broken == 1 else 'FAIL'))
    print('  после возврата: exit %d (ожидалось 0) %s' % (restored, 'OK' if restored == 0 else 'FAIL'))
    print('ИТОГ САМОТЕСТА ЗАМОРОЗКИ: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--snapshot', action='store_true')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--election', default='election:3')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.snapshot:
        return snapshot(a.election)
    if a.verify:
        return verify()
    print('ИСПОЛЬЗОВАНИЕ: method_freeze.py --snapshot | --verify | --self-test'); return 2


if __name__ == '__main__':
    sys.exit(main())
