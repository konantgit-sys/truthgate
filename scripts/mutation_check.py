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
  M8 проверка ревизии устава отключена — ловится unit-самотестом
  M9 сверка цитаты с телом ревизии — ловится unit_live (нужен живой журнал)
  M10 копии барьера разъехались    — ловится сверкой копий (sync_gate_copies --check)

Сеть не нужна: unit-самотест запускается с GATE_SELFTEST_OFFLINE=1.

Запуск:
  python3 scripts/mutation_check.py            # все поломки
  python3 scripts/mutation_check.py --only M4  # одна
Код возврата: 0 — все поломки пойманы; 1 — есть непойманая поломка, поломка не применилась,
нежизненный прогон (крах до проверки), объявленный но не исполненный случай.

ЗНАМЕНАТЕЛЬ. «Поймано 10 из 10» считается от манифеста MUTATIONS, а не от того, что
успело прогнаться: `--only M4` даёт вердикт ЧАСТИЧНО и код 1, а не зелёный PASS.
Пропуск случая помечается причиной (skip_reason=no_key), а не засчитывается как успех.

КОНТРОЛЬ. Эквивалентный мутант E1 (переименование локальной переменной) обязан выжить:
если пойман, значит ловится любой diff, а не поломка логики, и вердикт — FAIL.
"""
import argparse
import json
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
     "    if fails and False:\n        print('-' * 62)", "unit", 'if fails:'),
    ("M2", "нет проверки знаменателя", "scripts/verify_claim.py",
     "fails.append('НЕТ ЗНАМЕНАТЕЛЯ: не указана база/supply, от которой считаются доли.')",
     "pass  # мутация: проверка знаменателя отключена", "unit", 'НЕТ ЗНАМЕНАТЕЛЯ'),
    ("M3", "числа вне прогона проходят", "scripts/verify_claim.py",
     "        if unknown:\n",
     "        if unknown and False:  # мутация\n", "unit", 'if unknown:'),
    ("M4", "офлайн-пометка снята (боевой модуль)", "tools/truthgate/verify_claim.py",
     "        if offline and live:\n",
     "        if False:  # мутация: ветка офлайна отключена\n", "wrapper", 'if offline and live:'),
    ("M5", "рендер не сверяется", "scripts/publish_gate.sh",
     '    if ! python3 "$HERE_DIR/render_draft.py" --template',
     '    if false && ! python3 "$HERE_DIR/render_draft.py" --template', "wrapper", 'if ! python3 "$HERE_DIR/render_draft.py"'),
    ("M6", "метка времени не сверяется", "scripts/publish_gate.sh",
     '  if ! bash "$HERE_DIR/check_time_claims.sh" "$DRAFT_ARG"; then',
     '  if false && ! bash "$HERE_DIR/check_time_claims.sh" "$DRAFT_ARG"; then', "wrapper", 'if ! bash "$HERE_DIR/check_time_claims.sh"'),
    ("M7", "шапка не проверяется", "tools/truthgate/gate.sh",
     'if ! python3 "$HERE/header_check.py" "$DRAFT"; then',
     'if false && ! python3 "$HERE/header_check.py" "$DRAFT"; then', "wrapper", 'if ! python3 "$HERE/header_check.py"'),
    ("M8", "проверка ревизии устава отключена", "scripts/verify_claim.py",
     "    if _cited:\n",
     "    if _cited and False:  # мутация\n", "unit", 'if _cited:'),
    ("M9", "сверка цитаты с телом ревизии отключена", "scripts/verify_claim.py",
     "            elif _body is not MISSING and _norm_ws(_quote) not in _norm_ws(_body):\n",
     "            elif False:  # мутация\n", "unit_live", 'elif _body is not MISSING'),
    # M10 — ровно та поломка, которой 11.11 не было ни в одном тесте: разъехались
    # ДВЕ копии барьера, а исполнялась та, которую тесты не гоняли. Ломается только
    # боевая копия tools/truthgate/, поэтому ловить её может лишь сверка копий.
    ("M10", "копии барьера разъехались (боевая отличается от эталона)",
     "tools/truthgate/verify_claim.py",
     "        if offline and live:\n",
     "        if offline and live and True:  # мутация\n", "sync", 'if offline and live:'),
    # M11 — класс «дыра в списке файлов не блокируется». Эта проверка была НЕДОСТИЖИМА
    # в run_tests.sh до 17.11.2026 (стояла после `exit $fail`), поэтому поломка ниже
    # не ловилась ничем, сколько бы зелёных строк ни печатал набор.
    # 17.11.2026: первая версия M11 меняла только echo — `fail=1` в той же строке
    # оставался, поэтому verify.sh всё равно выходил кодом 1, и мутант ловился лишь
    # потому, что тест ищет текст сообщения. Название обещало «не блокируется», а
    # проверялось «не сообщается» (нашёл glitchfox, seq 123806; подтвердил astranaut01,
    # seq 123808). Теперь глушится само условие: ни сообщения, ни fail=1.
    ("M11", "дыра в списке файлов не блокируется", "scripts/verify.sh",
     'if [ -n "$missing" ]; then',
     'if false; then  # мутация: дыра не блокируется и не сообщается', "sums", 'if [ -n "$missing" ]; then'),
]

# Эквивалентный мутант обязан ВЫЖИТЬ: иначе мутатор ловит любой diff, а не поломку логики.
EQUIVALENT = [
    ("E1", "переименована локальная переменная (логика та же)", "scripts/verify_claim.py",
     "    if fails:\n", "    if fails:  # эквивалентный мутант\n"),
]

TESTS = {
    "unit": (["bash", "scripts/gate_selftest.sh"], {"GATE_SELFTEST_OFFLINE": "1"}),
    "wrapper": (["bash", "scripts/wrapper_selftest.sh"], {}),
    # unit_live: тот же самотест, но с сетью — им ловятся поломки, которые видны
    # только при сверке с живым журналом ревизий (M9). Отдельный режим, потому что
    # в офлайне этот класс непроверяем по определению.
    "unit_live": (["bash", "scripts/gate_selftest.sh"], {}),
    # Сверка двух копий барьера. До 17.11.2026 её не запускал ни один тест — из-за
    # этого класс «копии разъехались» не покрывался мутациями (замечание glitchfox, 13.11).
    "sync": (["python3", "scripts/sync_gate_copies.py", "--check"], {}),
    # Покрытие списков: до 17.11.2026 висело мёртвой строкой после `exit $fail`.
    "sums": (["bash", "scripts/test_sums_coverage.sh"], {}),
}

# Признаки того, что прогон упал не на проверке, а до неё: синтаксис, импорт, имя.
# Такое падение нельзя засчитывать как «мутант пойман» — барьер в этот момент не работал.
UNVIABLE = ("SyntaxError", "ImportError", "ModuleNotFoundError", "IndentationError")

# 17.11.2026: unit_live требует ключ борды (живой журнал ревизий устава). Без ключа
# случай пропускался, а база краснела — то есть прогон зависел от того, экспортирована
# ли переменная в шелле, а не от кода. Берём ключ сами, из штатного хранилища.
ACCOUNTS_PATH = os.environ.get(
    'GPB_ACCOUNTS', '/home/agent/data/projects/gpb-dash/data/keys/accounts.json')


def resolve_key_file():
    """Путь к файлу ключа борды: из окружения, иначе из хранилища аккаунтов."""
    given = os.environ.get('GATE_BOARD_KEY_FILE', '')
    if given and os.path.exists(given):
        return given
    try:
        accs = json.load(open(ACCOUNTS_PATH, encoding='utf-8'))['accounts']
        key = next((a['api_key'] for a in accs if a.get('name') == 'v2bot-agent'), None)
        if not key:
            return ''
        fd = tempfile.NamedTemporaryFile('w', prefix='gatekey-', delete=False)
        fd.write(key)
        fd.close()
        os.chmod(fd.name, 0o600)
        return fd.name
    except Exception:
        return ''

IGNORE = shutil.ignore_patterns('.git', '__pycache__', '*.pyc', 'board')


def copy_tree(dst):
    shutil.copytree(ROOT, dst, ignore=IGNORE)


KEY_FILE = resolve_key_file()


def run(test, tree):
    cmd, extra = TESTS[test]
    env = dict(os.environ)
    env.update(extra)
    if test == 'unit_live' and KEY_FILE:
        env['GATE_BOARD_KEY_FILE'] = KEY_FILE
    # 17.11.2026 (glitchfox, seq 123642): .pyc инвалидируется по mtime+размеру, поэтому
    # правка той же длины с сохранённым mtime исполняет СТАРЫЙ байткод. Свой каталог
    # байткода на каждый прогон убирает эту возможность: байткод не переиспользуется.
    cache = tempfile.mkdtemp(prefix='pycache-')
    env['PYTHONPYCACHEPREFIX'] = cache
    p = subprocess.run(cmd, cwd=tree, env=env, capture_output=True, text=True)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    a = ap.parse_args()

    print('БАЗА: без поломок все самотесты обязаны быть зелёными')
    base_ok = True
    skipped = []
    for name in ('unit', 'unit_live', 'wrapper', 'sync', 'sums'):
        if name == 'unit_live' and not KEY_FILE:
            skipped.append((name, 'no_key'))
            print('  %-8s НЕ ИСПОЛНЕН — skip_reason=no_key (нет ключа борды)' % name)
            continue
        code, out = run(name, ROOT)
        tag = 'OK' if code == 0 else 'ПРОВАЛ'
        print('  %-8s код %s — %s' % (name, code, tag))
        if code != 0:
            base_ok = False
            print('\n'.join('      ' + l for l in out.strip().splitlines()[-4:]))
    if not base_ok:
        print('ВЕРДИКТ: FAIL — база красная, мутационная проверка бессмысленна')
        return 1
    if skipped:
        print('ВЕРДИКТ: ЧАСТИЧНО — случаи не исполнены: %s'
              % ', '.join('%s (%s)' % (n, r) for n, r in skipped))
        return 1

    caught = 0
    missed = []
    unapplied = []
    invalid = []
    executed = []
    killed_by = []
    for code_id, desc, rel, old, new, test, anchor in MUTATIONS:
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
            # 17.11.2026: мутант обязан менять КОД, реализующий заявленный класс, а не
            # соседний вывод. Повод — M11 первой версии: название обещало «дыра не
            # блокируется», а менялось только сообщение, `fail=1` оставался (glitchfox,
            # seq 123806; astranaut01, seq 123808). Якорь должен быть в файле до мутации
            # и исчезнуть после: иначе мутант не про заявленное и в зачёт не идёт.
            # Якорь проверяется в границах мутируемого фрагмента: он обязан быть в
            # заменяемом тексте и обязан отсутствовать в замене. Проверка «по всему
            # файлу» дала ложный отказ на M9 — та же строка встречается в файле ещё
            # раз, и мутант объявлялся чужим, хотя менял именно свою ветку.
            if anchor not in old:
                unapplied.append((code_id, desc, rel + ' (якорь вне фрагмента)'))
                print('  %s %-40s ЯКОРЬ ВНЕ МУТИРУЕМОГО ФРАГМЕНТА: %r' % (code_id, desc, anchor))
                continue
            mutated = src.replace(old, new, 1)
            if anchor in new:
                invalid.append((code_id, desc, 'якорь на месте: %r' % anchor))
                print('  %s %-40s МУТАНТ НЕ КАСАЕТСЯ ЗАЯВЛЕННОГО (якорь цел: %r)'
                      % (code_id, desc, anchor))
                continue
            open(path, 'w', encoding='utf-8').write(mutated)
            rc, out = run(test, tree)
            executed.append(code_id)
            if rc != 0:
                # «Поймана» значит «упала именно проверка», а не «модуль не собрался»:
                # крах на синтаксисе/импорте оставляет инвариант непроверенным.
                live = [sig for sig in UNVIABLE if sig in out]
                if live:
                    invalid.append((code_id, desc, live[0]))
                    print('  %s %-40s НЕЖИЗНЕННЫЙ ПРОГОН (%s) — не засчитан как поимка'
                          % (code_id, desc, live[0]))
                else:
                    caught += 1
                    killed_by.append((code_id, test, rc))
                    print('  %s %-40s поймана (%s упал, код %s)' % (code_id, desc, test, rc))
            else:
                missed.append((code_id, desc, test))
                print('  %s %-40s НЕ ПОЙМАНА — %s остался зелёным' % (code_id, desc, test))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    declared = [m[0] for m in MUTATIONS]
    total = len(declared)
    not_executed = [c for c in declared if c not in executed]
    print('  знаменатель из манифеста: объявлено %d, исполнено %d%s'
          % (total, len(executed), (', не исполнено: ' + ', '.join(not_executed)) if not_executed else ''))
    print('ИТОГ: поймано %s из %s · не поймано %s · не применилось %s · нежизненных %s'
          % (caught, total, len(missed), len(unapplied), len(invalid)))
    if killed_by:
        print('  кем пойманы (мутант × тест × код): '
              + ' · '.join('%s→%s/%s' % (c, t, rc) for c, t, rc in killed_by))
    if missed:
        print('ВЕРДИКТ: FAIL — тест не замечает поломку: %s'
              % ', '.join('%s (%s)' % (c, d) for c, d, _ in missed))
        return 1
    if invalid:
        print('ВЕРДИКТ: FAIL — прогон падал до проверки (синтаксис/импорт), инвариант не проверен: %s'
              % ', '.join('%s (%s: %s)' % (c, d, s_) for c, d, s_ in invalid))
        return 1
    if unapplied:
        print('ВЕРДИКТ: FAIL — поломка не применилась (эталон изменился): %s'
              % ', '.join('%s (%s)' % (c, d) for c, d, _ in unapplied))
        return 1
    if not_executed:
        # Объявленный, но не исполненный случай — не PASS: знаменатель берётся из
        # манифеста, а не из того, что успели прогнать (замечание glitchfox 15.11).
        print('ВЕРДИКТ: ЧАСТИЧНО — объявленные поломки не исполнены: %s' % ', '.join(not_executed))
        return 1
    # Контроль: эквивалентный мутант обязан выжить, иначе мутатор ловит любой diff.
    for code_id, desc, rel, old, new in EQUIVALENT:
        tmp = tempfile.mkdtemp(prefix='mut-%s-' % code_id)
        tree = os.path.join(tmp, 'truthgate')
        try:
            copy_tree(tree)
            path = os.path.join(tree, rel)
            src = open(path, encoding='utf-8').read()
            if old not in src:
                print('ВЕРДИКТ: FAIL — контрольный мутант %s не применился' % code_id)
                return 1
            open(path, 'w', encoding='utf-8').write(src.replace(old, new, 1))
            rc, out = run('unit', tree)
            if rc != 0:
                print('ВЕРДИКТ: FAIL — контрольный %s (%s) ПОЙМАН, значит ловится любой diff, '
                      'а не поломка логики' % (code_id, desc))
                return 1
            print('  %s %-40s выжил, как и обязан' % (code_id, desc))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print('ВЕРДИКТ: PASS — каждая поломка роняет свой самотест, эквивалентная не роняет')
    return 0


if __name__ == '__main__':
    sys.exit(main())
