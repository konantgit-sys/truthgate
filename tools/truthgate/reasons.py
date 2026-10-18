#!/usr/bin/env python3
"""Единый словарь кодов отказа шлюза truthgate.

Зачем этот файл. До 18.10.2026 шлюз отвечал одним «не 0» на любой отказ, и тест
довольствовался этим: кейс считался пройденным, если код вообще не ноль. Значит
кейс «расхождение с живым ответом» проходил и тогда, когда черновик падал на
отсутствии шапки, — тест проверял не ту причину, которую называл. Разные отказы
обязаны быть различимы по коду, иначе потребитель (тест, публикатор, человек)
не может отличить «шлюз поймал подмену числа» от «шлюз не нашёл файл».

Контракт кодов:
  0   PASS
  2   USAGE             — неверный вызов (нет аргументов)
  10  DRAFT_MISSING     — нет файла черновика
  11  FACTS_MISSING     — нет файла фактов
  12  HEADER            — шапка Role/Post type/Data status/Conflict, метки
  13  DENOMINATOR       — нет знаменателя (базы расчёта)
  14  CONTROL_NOT_EXECUTABLE — контроль без исполняемого live-блока
  15  CONTROL_LIVE      — живой контроль: не ответил, расходится, пуст, неполон
  16  NUMBERS_NOT_IN_FACTS — числа в тексте, которых нет в facts.numbers
  17  EMPTY_DRAFT       — пустой черновик
  18  RENDER_MISMATCH   — текст не совпал с рендером из фактов (число правили руками)
  19  TIME_MISMATCH     — метка времени в тексте расходится с часами
  20  NO_ALTERNATIVE    — не сформулировано конкурирующее объяснение
  21  NO_NUMBERS_IN_FACTS — в черновике числа, а numbers пуст
  22  TEMPLATE_PLACEHOLDER — остались неподставленные {{ключи}}
  23  NO_SOURCE         — нет обязательного поля источника/окна
  1   GENERIC           — отказ без опознанной причины (резерв, должен быть пуст)

Правило: код 1 в норме не встречается. Если он появился — значит в verify_claim
добавили отказ, не приписав ему причину; это дефект самого словаря.
"""
from __future__ import annotations

CODES: dict[str, tuple[int, str]] = {
    "USAGE": (2, "неверный вызов"),
    "DRAFT_MISSING": (10, "нет файла черновика"),
    "FACTS_MISSING": (11, "нет файла фактов"),
    "HEADER": (12, "шапка/метки не в порядке"),
    "DENOMINATOR": (13, "нет знаменателя"),
    "CONTROL_NOT_EXECUTABLE": (14, "контроль без live-блока"),
    "CONTROL_LIVE": (15, "живой контроль не выполнен/расходится"),
    "NUMBERS_NOT_IN_FACTS": (16, "числа вне прогона"),
    "EMPTY_DRAFT": (17, "пустой черновик"),
    "RENDER_MISMATCH": (18, "текст не совпал с рендером"),
    "TIME_MISMATCH": (19, "метка времени расходится"),
    "NO_ALTERNATIVE": (20, "нет альтернативы"),
    "NO_NUMBERS_IN_FACTS": (21, "числа в тексте, numbers пуст"),
    "TEMPLATE_PLACEHOLDER": (22, "остались {{ключи}}"),
    "NO_SOURCE": (23, "нет обязательного поля источника/окна"),
    "GENERIC": (1, "отказ без опознанной причины"),
}

# Порядок разбора: от самой содержательной причины к самой внешней. Число вне
# прогона важнее формы шапки — это и есть та подмена, ради которой барьер стоит.
MARKERS: list[tuple[str, str]] = [
    # «numbers пуст» идёт раньше «числа вне прогона»: при пустом списке оба
    # сообщения появляются одновременно, и пустой список — причина, а не следствие.
    ("НЕТ ЧИСЕЛ В FACTS", "NO_NUMBERS_IN_FACTS"),
    ("ЧИСЛА ВНЕ ПРОГОНА", "NUMBERS_NOT_IN_FACTS"),
    ("НЕЗАПОЛНЕННЫЙ ШАБЛОН", "TEMPLATE_PLACEHOLDER"),
    ("ПУСТОЙ ЧЕРНОВИК", "EMPTY_DRAFT"),
    ("CONTROL.LIVE РАСХОДИТСЯ", "CONTROL_LIVE"),
    ("CONTROL.LIVE НЕ ОТВЕТИЛ", "CONTROL_LIVE"),
    ("CONTROL.LIVE ПУСТ", "CONTROL_LIVE"),
    ("CONTROL.LIVE НЕПОЛОН", "CONTROL_LIVE"),
    ("CONTROL.LIVE:", "CONTROL_LIVE"),
    ("КОНТРОЛЬ НЕ ИСПОЛНЯЕМЫЙ", "CONTROL_NOT_EXECUTABLE"),
    ("НЕТ КОНТРОЛЯ", "CONTROL_NOT_EXECUTABLE"),
    ("НЕТ ЗНАМЕНАТЕЛЯ", "DENOMINATOR"),
    ("НЕТ АЛЬТЕРНАТИВЫ", "NO_ALTERNATIVE"),
    (": не указан (", "NO_SOURCE"),
    ("АЛЬТЕРНАТИВА: неизвестные ключи", "NO_ALTERNATIVE"),
]


def classify(fails: list[str]) -> str:
    """Имя причины отказа.

    Порядок разбора — порядок самих проверок в verify_claim (знаменатель → контроль
    → альтернатива → источник → числа). Берётся ПЕРВОЕ фатальное сообщение, у
    которого опознан маркер: 18.10.2026 приоритет по «важности» давал коду 16
    (числа) перебивать 13/14/15/20/23, и тест снова не мог отличить причину.
    """
    for f in fails:
        for marker, name in MARKERS:
            if marker in f:
                return name
    return "GENERIC"


def exit_code(fails: list[str]) -> int:
    name = classify(fails)
    return CODES[name][0]


def describe(name: str) -> str:
    code, title = CODES.get(name, CODES["GENERIC"])
    return f"{code} {name} — {title}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--table":
        for name, (code, title) in sorted(CODES.items(), key=lambda kv: kv[1][0]):
            print(f"{code:>3}  {name:<24} {title}")
        sys.exit(0)
    print("ИСПОЛЬЗОВАНИЕ: reasons.py --table")
    sys.exit(2)
