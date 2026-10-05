#!/usr/bin/env python3
"""Тест сторожа заморозки на дырявом входе.

Сторож обязан блокировать правку замороженного файла без записи с сегодняшней
датой — и пропускать её, когда запись есть. Если ни один случай не блокируется,
проверкой это считать нельзя. Код возврата: 0 — тест прошёл, 1 — не прошёл.
"""
import datetime, hashlib, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# корень дерева берётся из окружения, если задан
ROOT_BASE = os.environ.get("FREEZE_ROOT", os.path.dirname(HERE))
GUARD = os.path.join(HERE, 'scripts', 'freeze_guard.py')
BOX = '/tmp/freeze-guard-test'
TODAY = datetime.datetime.utcnow().strftime('%d.%m.%Y')


def prep():
    shutil.rmtree(BOX, ignore_errors=True)
    os.makedirs(os.path.join(BOX, 'root', 'board'))
    f = os.path.join(BOX, 'root', 'board', 'doc.md')
    open(f, 'w', encoding='utf-8').write('версия один\n')
    h = hashlib.sha256(open(f, 'rb').read()).hexdigest()
    json.dump({'files': {'board/doc.md': {'sha256': h}}},
              open(os.path.join(BOX, 'freeze.json'), 'w', encoding='utf-8'))
    open(os.path.join(BOX, 'ledger.md'), 'w', encoding='utf-8').write('# реестр\n')
    return f


def run():
    r = subprocess.run([sys.executable, GUARD, '--freeze', os.path.join(BOX, 'freeze.json'),
                        '--ledger', os.path.join(BOX, 'ledger.md'),
                        '--root', os.path.join(BOX, 'root'), '--quiet'],
                       capture_output=True, text=True)
    return r.returncode


def add_entry(path_line, date=TODAY):
    with open(os.path.join(BOX, 'ledger.md'), 'a', encoding='utf-8') as f:
        f.write('\n### C-0001 — тест\n\n- **published_at:** %s\n- **files:** %s\n' % (date, path_line))


def main():
    cases = []

    f = prep()
    cases.append(('файл не менялся', run(), 0))

    f = prep()
    open(f, 'a', encoding='utf-8').write('правка без записи\n')
    cases.append(('правка без записи', run(), 1))

    f = prep()
    open(f, 'a', encoding='utf-8').write('правка\n')
    add_entry('board/other-file.md')
    cases.append(('запись про другой файл', run(), 1))

    f = prep()
    open(f, 'a', encoding='utf-8').write('правка\n')
    add_entry('board/doc.md', '01.01.2020')
    cases.append(('запись с чужой датой', run(), 1))

    f = prep()
    open(f, 'a', encoding='utf-8').write('правка\n')
    add_entry('board/doc.md')
    cases.append(('запись с сегодняшней датой и верным путём', run(), 0))

    f = prep()
    os.remove(f)
    cases.append(('файл пропал без записи', run(), 1))

    ok = 0
    for name, got, want in cases:
        good = got == want
        ok += good
        print('  [%s] %s — код %d, ожидался %d' % ('PASS' if good else 'FAIL', name, got, want))
    print('ИТОГ: %d из %d' % (ok, len(cases)))
    return 0 if ok == len(cases) else 1


if __name__ == '__main__':
    sys.exit(main())
