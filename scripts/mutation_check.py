#!/usr/bin/env python3
"""Мутационная проверка барьера: тест обязан ПАДАТЬ, когда барьер ослаблен.

ЗАЧЕМ. 11.11.2026 выяснилось, что проверка барьера может быть «зелёной» и при
этом не проверять ничего: сверка копий `sync_gate_copies.py` не запускалась,
две версии барьера разъехались, и все отчёты «6/6» относились к файлу, который
обёртка `publish_gate.sh` в бою не исполняет. Ошибка была не в тестах, а в том,
что никто не проверил: а способны ли тесты вообще покраснеть.

Этот скрипт отвечает на этот вопрос замером. Он берёт копию дерева, вносит в
барьер РОВНО одну поломку и требует, чтобы соответствующий самотест упал.
Если после поломки самотест остаётся зелёным — поломка не ловится, и это
печатается как ПРОВАЛ, а не как «ну ладно».

Поломки покрывают разные классы:
  M1 вердикт всегда PASS          — ловится unit-самотестом (gate_selftest.sh)
  M2 нет проверки знаменателя     — ловится unit-самотестом
  M3 числа вне прогона проходят   — ловится unit-самотестом
  M4 офлайн-пометка снята         — ловится самотестом обёртки (wrapper_selftest.sh)
  M5 рендер не сверяется          — ловится самотестом обёртки
  M6 метка времени не сверяется   — ловится самотестом обёртки
  M7 шапка не проверяется         — ловится самотестом обёртки

Сеть не нужна: unit-самотест запускается с GATE_SELFTEST_OFFLINE=1.

Запуск:
  python3 scripts/mutation_check.py            # все поломки
  python3 scripts/mutation_check.py --only M4  # одна
Код возврата: 0 — все поломки пойманы; 1 — есть непойманая поломка или поломка не применилась.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (код, описание, файл, что заменить, на что заменить, какой тест обязан упасть)
MUTATIONS = [
    ("M1", "вердикт всегда PASS", "scripts/verify_claim.py",
     "    if fails:\n        print('-' * 62)",
     "    if fails and False:\n        print('-' * 62)", "unit"),
    ("M2", "нет проверки знаменателя", "scripts/verify_claim.py",
     "fails.append('НЕТ ЗНАМЕНАТЕЛЯ: не указана база/supply, от которой считаются доли.')",
     "pass  # мутация: проверка знаменателя отключена", "unit"),
    ("M3", "числа вне прогона проходят", "scripts/verify_claim.py",
     "        if unknown:\n",
     "        if unknown and False:  # мутация\n", "unit"),
    ("M4", "офлайн-пометка снята (боевой модуль)", "tools/truthgate/verify_claim.py",
     "        if offline and live:\n",
     "        if False:  # мутация: ветка офлайна отключена\n", "wrapper"),
    ("M5", "рендер не сверяется", "scripts/publish_gate.sh",
     '    if ! python3 "$HERE_DIR/render_draft.py" --template',
     '    if false && ! python3 "$HERE_DIR/render_draft.py" --template', "wrapper"),
    ("M6", "метка времени не сверяется", "scripts/publish_gate.sh",
     '  if ! bash "$HERE_DIR/check_time_claims.sh" "$DRAFT_ARG"; then',
     '  if false && ! bash "$HERE_DIR/check_time_claims.sh" "$DRAFT_ARG"; then', "wrapper"),
    ("M7", "шапка не проверяется", "tools/truthgate/gate.sh",
     'if ! python3 "$HERE/header_check.py" "$DRAFT"; then',
     'if false && ! python3 "$HERE/header_check.py" "$DRAFT"; then', "wrapper"),
]

TESTS = {
    "unit": (["bash", "scripts/gate_selftest.sh"], {"GATE_SELFTEST_OFFLINE": "1"}),
    "wrapper": (["bash", "scripts/wrapper_selftest.sh"], {}),
}

IGNORE = shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'board')


def copy_tree(dst):
    shutil.copytree(ROOT, dst, ignore=IGNORE)


def run(test, tree):
    cmd, extra = TESTS[test]
    env = dict(os.environ)
    env.update(extra)
    p = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    a = ap.parse_args()

    print('БАЗА: без поломок оба самотеста обязаны быть зелёными')
    base_ok = True
    for name in ('unit', 'wrapper'):
        code, out = run(name, ROOT)
        tag = 'OK' if code == 0 else 'ПРОВАЛ'
        print('  %-8s код %s — %s' % (name, code, tag))
        if code != 0:
            base_ok = False
            print('\n'.join('      ' + l for l in out.strip().splitlines()[-4:]))
    if not base_ok:
        print('ВЕРДИКТ: FAIL — база красная, мутационная проверка бессмысленна')
        return 1

    caught = 0
    missed = []
    unapplied = []
    for code_id, desc, rel, old, new, test in MUTATIONS:
        if a.only and a.only != code_id:
            continue
        tmp = tempfile.mkdtemp(prefix='mut-%s-' % code_id)
        tree = os.path.join(tmp, 'truthgate')
        try:
            copy_tree(tree)
            path = os.path.join(tree, rel)
            src = open(path, encoding='utf-8').read()
            if old not in src:
                unapplied.append((code_id, desc, rel))
                print('  %s %-40s ПОЛОМКА НЕ ПРИМЕНИЛАСЬ (%s)' % (code_id, desc, rel))
                continue
            open(path, 'w', encoding='utf-8').write(src.replace(old, new, 1))
            rc, out = run(test, tree)
            if rc != 0:
                caught += 1
                print('  %s %-40s поймана (%s упал, код %s)' % (code_id, desc, test, rc))
            else:
                missed.append((code_id, desc, test))
                print('  %s %-40s НЕ ПОЙМАНА — %s остался зелёным' % (code_id, desc, test))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    total = caught + len(missed) + len(unapplied)
    print('ИТОГ: поймано %s из %s' % (caught, total))
    if missed:
        print('ВЕРДИКТ: FAIL — тест не замечает поломку: %s'
              % ', '.join('%s (%s)' % (c, d) for c, d, _ in missed))
        return 1
    if unapplied:
        print('ВЕРДИКТ: FAIL — поломка не применилась (эталон изменился): %s'
              % ', '.join('%s (%s)' % (c, d) for c, d, _ in unapplied))
        return 1
    print('ВЕРДИКТ: PASS — каждая поломка роняет свой самотест, значит проверки не пустые')
    return 0


if __name__ == '__main__':
    sys.exit(main())
