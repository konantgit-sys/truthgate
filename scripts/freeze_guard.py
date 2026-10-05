#!/usr/bin/env python3
"""Механический сторож заморозки: правка замороженного файла без записи в реестр не проходит.

Смысл: правило «изменения только через реестр исправлений» не должно держаться на
честном слове. Сторож сверяет текущие хэши с снимком и требует, чтобы у каждого
изменившегося файла была запись в реестре с сегодняшней датой и упоминанием пути.

Код возврата: 0 — нарушений нет, 1 — есть незаписанное изменение, 2 — ошибка вызова.
Запуск: python3 scripts/freeze_guard.py [--freeze F] [--ledger L] [--root R] [--today YYYY-MM-DD]
"""
import argparse, datetime, hashlib, json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# корень, относительно которого считаются пути манифеста
# корень дерева берётся из окружения, если задан
ROOT_BASE = os.environ.get("FREEZE_ROOT", os.path.dirname(HERE))
# Публичная копия не знает раскладки рабочего дерева: снимок заморозки задаётся
# аргументом или переменной окружения, по умолчанию берётся приложенный пример.
DEF_FREEZE = os.environ.get('FREEZE_MANIFEST',
                            os.path.join(HERE, 'manifests', 'example-freeze.json'))
DEF_LEDGER = os.environ.get('FREEZE_LEDGER', os.path.join(HERE, 'ledger', 'CORRECTIONS.md'))


def sha(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def ledger_blocks(path):
    """Блоки реестра: текст + дата из published_at."""
    if not os.path.exists(path):
        return []
    text = open(path, encoding='utf-8').read()
    blocks = []
    # реестр может нумеровать записи как '## C-0001', так и '### C-0001':
    # принимаем оба уровня, иначе записанное изменение выглядит незаписанным
    for chunk in re.split(r'\n(?=#{2,}\s)', text):
        if not re.match(r'#{2,}\s', chunk):
            continue
        # формат реестра: «- **published_at:** 05.10.2026». Звёздочки могут стоять
        # и до, и после двоеточия — иначе дата не парсится и запись выглядит как без даты
        m = re.search(r'published_at\s*[*_]{0,2}\s*[:：][*_]{0,2}\s*([0-9]{2}\.[0-9]{2}\.[0-9]{4})', chunk)
        blocks.append({'date': m.group(1) if m else None, 'text': chunk})
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--freeze', default=DEF_FREEZE)
    ap.add_argument('--ledger', default=DEF_LEDGER)
    ap.add_argument('--root', default=os.environ.get('FREEZE_ROOT', HERE))
    ap.add_argument('--today', default=None)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    try:
        frozen = json.load(open(a.freeze, encoding='utf-8')).get('files') or {}
    except Exception as e:
        print('ошибка чтения снимка: %s' % e)
        return 2
    if not frozen:
        print('в снимке нет списка файлов')
        return 2

    today = a.today or datetime.datetime.utcnow().strftime('%d.%m.%Y')
    blocks = ledger_blocks(a.ledger)

    def recorded(rel):
        for b in blocks:
            # без разобранной даты запись не считается доказательством: «непонятно когда» != «сегодня»
            if rel in b['text'] and b['date'] == today:
                return True
        return False

    violations, changed, missing = [], [], []
    for rel, meta in sorted(frozen.items()):
        full = os.path.join(a.root, rel)
        if not os.path.exists(full):
            missing.append(rel)
            if not recorded(rel):
                violations.append(('%s' % rel, 'файл отсутствует, записи в реестре нет'))
            continue
        cur = sha(full)
        if cur != meta.get('sha256'):
            changed.append(rel)
            if not recorded(rel):
                violations.append((rel, 'хэш разошёлся с снимком, записи с сегодняшней датой нет'))

    if not a.quiet:
        print('снимок: %s | файлов %d | изменилось %d | отсутствует %d'
              % (os.path.basename(a.freeze), len(frozen), len(changed), len(missing)))
        print('реестр: %s | блоков %d | дата проверки %s'
              % (os.path.basename(a.ledger), len(blocks), today))
    if violations:
        for rel, why in violations:
            print('НАРУШЕНИЕ: %s — %s' % (rel, why))
        print('ИТОГ: незаписанных изменений %d — коммит и выпуск запрещены' % len(violations))
        return 1
    print('ИТОГ: все изменения замороженных файлов записаны в реестр')
    return 0


if __name__ == '__main__':
    sys.exit(main())
