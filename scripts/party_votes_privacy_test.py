#!/usr/bin/env python3
"""Тест утечки в публикации агрегатов партийных голосований.

Проверка на дырявом входе: тест обязан ЗАБЛОКИРОВАТЬ старый набор правил
(k>=5 только на каждую клетку) и пропустить новый. Код возврата:
  0 — утечки не найдено (правила держат),
  1 — утечка воспроизведена (правила не держат),
  2 — ошибка вызова.
Запуск: python3 scripts/party_votes_privacy_test.py --rules old|new
"""
import argparse, sys

ROSTER = 9                      # состав партии (замороженный на выпуск)
TOPICS = {'A': 6, 'B': 3, 'C': 5}   # голоса «за» по темам в этом выпуске
TOTAL_YES_PUBLISHED = sum(TOPICS.values())
SUPPRESS_BELOW = 5


def old_rules():
    return {'complementary': False, 'suppress_total': False, 'leader_line_always': True,
            'merge_on_roster_change': False, 'publish_changer_identity': True}


def new_rules():
    return {'complementary': True, 'suppress_total': False, 'leader_line_always': False,
            'merge_on_roster_change': True, 'publish_changer_identity': False}


def check_single_cell(rules):
    """Клетка меньше порога: скрыть одну клетку и оставить итог = утечка через дополнение."""
    small = [t for t, v in TOPICS.items() if v < SUPPRESS_BELOW]
    if not small:
        return ('нет мелких клеток', 'safe')
    cell = small[0]
    if not rules['complementary']:
        recovered = TOTAL_YES_PUBLISHED - sum(v for t, v in TOPICS.items() if t != cell)
        return ('клетка %s восстановлена из итога: %d' % (cell, recovered), 'LEAK')
    # дополнительное подавление: скрываем ещё одну клетку, итог перестаёт замыкать одну неизвестную
    hidden = small + [t for t in TOPICS if t not in small][:1]
    known = sum(v for t, v in TOPICS.items() if t not in hidden)
    candidates = [(a, b) for a in range(ROSTER + 1) for b in range(ROSTER + 1)
                  if a + b == TOTAL_YES_PUBLISHED - known]
    if len(candidates) < 2:
        return ('дополнительное подавление не сработало', 'LEAK')
    return ('двух скрытых клеток не хватает: вариантов %d' % len(candidates), 'safe')


def check_leader_line(rules):
    """Строка лидера + скрытая мелкая клетка = утечка на меньшем составе."""
    small = [t for t, v in TOPICS.items() if v < SUPPRESS_BELOW]
    if not small:
        return ('нет мелких клеток', 'safe')
    if rules['leader_line_always'] and not rules['complementary']:
        return ('голос лидера раскалывает скрытую клетку с составом %d' % ROSTER, 'LEAK')
    if rules['leader_line_always'] and rules['complementary']:
        return ('строка лидера остаётся, но две скрытые клетки дают неоднозначность', 'safe')
    return ('строка лидера не публикуется для скрытых клеток', 'safe')


def check_cross_release(rules):
    """Смена состава между выпусками: разница итогов выдаёт, кто поменял голос."""
    r1, r2 = {'B': 3}, {'B': 4}
    delta = r2['B'] - r1['B']
    if rules['merge_on_roster_change'] and not rules['publish_changer_identity']:
        # период слит, состав подан числом без имени: разница приписана выпуску, а не человеку
        candidates = ROSTER - abs(delta) if ROSTER > abs(delta) else 0
        if candidates >= 2:
            return ('смена состава не названа по имени: подозреваемых %d' % candidates, 'safe')
        return ('слияние периодов не помогло', 'LEAK')
    return ('разницу %+d видно, и названный сменивший голос опознаётся' % delta, 'LEAK')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rules', choices=('old', 'new'), required=True)
    a = ap.parse_args()
    rules = old_rules() if a.rules == 'old' else new_rules()
    checks = (('одна клетка ниже порога', check_single_cell),
              ('строка лидера', check_leader_line),
              ('смена состава между выпусками', check_cross_release))
    leaks = 0
    print('правила: %s | состав %d | порог скрытия %d' % (a.rules, ROSTER, SUPPRESS_BELOW))
    for name, fn in checks:
        detail, verdict = fn(rules)
        leaks += (verdict == 'LEAK')
        print('  [%s] %s — %s' % ('УТЕЧКА' if verdict == 'LEAK' else 'ок', name, detail))
    if leaks:
        print('ИТОГ: правила НЕ держат, утечек %d — выпуск запрещён' % leaks)
        return 1
    print('ИТОГ: утечек не найдено')
    return 0


if __name__ == '__main__':
    sys.exit(main())
