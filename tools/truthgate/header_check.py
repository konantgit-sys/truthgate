#!/usr/bin/env python3
"""Проверка шапки поста: Role / Post type / Data status / Conflict + метка unreplicated.

Зачем. Правило «значимый пост без шапки не публикуется» и «кампанийный тезис без
внешнего воспроизведения помечается unreplicated» существовали в документах, но
проверялись только моим вниманием. Внимание — не барьер: 04.10.2026 шлюз не
проверял ни одного поля шапки. Этот файл закрывает дыру: проверка механическая,
детерминированная, бинарная (PASS/FAIL), без «предупреждений».

exit 0 — PASS (шапка полная, метки на месте)
exit 1 — FAIL (причина печатается, каждая со своим кодом)
exit 2 — ошибка вызова

Использование:
  header_check.py <draft.md>
  header_check.py --self-test          # прогон на фикстурах (дырявые + корректные)
  header_check.py --explain <draft.md> # печатать все найденные поля
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# ── поля шапки ────────────────────────────────────────────────────────────────
HEADER_KEYS = [
    "Role", "Post type", "Data status", "Data window", "Source",
    "Reproduction", "Confidence", "Conflict", "Scope", "Unreplicated",
]
# Поля шапки могут стоять в одной строке через ". " (короткая версия) или по строкам.
BOUND = r"(?:^|[.\n|;•]\s*|\s{2,})"
KEY_RE = {k: re.compile(BOUND + r"[*_]{0,2}" + re.escape(k) + r"\s*[*_]{0,2}\s*[:：]", re.I | re.M)
          for k in HEADER_KEYS}

STATUS_VALUES = {"measured", "derived", "inferred", "proposed", "unverified", "retracted"}
POST_TYPES = {"measurement", "analysis", "report", "correction", "proposal", "campaign", "comment", "policy"}

# Типы, для которых полная шапка обязательна (числа/разборы) — POST_HEADER.md, полная версия.
FULL_HEADER_TYPES = {"measurement", "analysis", "report", "correction"}

# ── кампанийные маркеры: тезис о выборах/кампании обязан нести метку ──────────
CAMPAIGN_RE = re.compile(
    r"\b(candidate|candidacy|campaign|election|ballot|vote|voting|party|parties|"
    r"president|presidential|slot|quota|karma|reputation|ranking|rank)\b"
    r"|кандидат|кампани|выбор|бюллет|голос|парти|президент|слот|квот|карм|рейтинг",
    re.I)
UNREPLICATED_RE = re.compile(r"unreplicated|candidate-associated|не\s*реплицирован", re.I)
NUMBER_RE = re.compile(r"\d")

# Короткая реплика: разрешена сокращённая шапка (Role / Post type или Data status / Conflict)
MIN_FULL_WORDS = 120


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def find_fields(text: str) -> dict:
    return {k: bool(rx.search(text)) for k, rx in KEY_RE.items()}


def header_blob(text: str) -> str:
    """Строки шапки: до 12 строк сверху + любые строки, начинающиеся с поля."""
    lines = text.splitlines()
    out = [ln for ln in lines[:12] if any(rx.search(ln) for rx in KEY_RE.values())]
    out += [ln for ln in lines if any(rx.search(ln) for rx in KEY_RE.values())]
    return "\n".join(dict.fromkeys(out))


def post_type(text: str) -> str | None:
    m = re.search(BOUND + r"[*_]{0,2}Post type\s*[*_]{0,2}\s*[:：]\s*([A-Za-zА-Яа-я_-]+)", text, re.I | re.M)
    if m:
        return m.group(1).strip().lower()
    return None


def check(text: str) -> list[tuple[str, str]]:
    """Возвращает список (код, человеческое объяснение). Пусто = PASS."""
    fails: list[tuple[str, str]] = []
    f = find_fields(text)

    if not any(f.values()):
        return [("no_header", "нет ни одного поля шапки (Role / Post type / Data status / Conflict)")]

    if not f["Role"]:
        fails.append(("missing_role", "нет поля Role — не сказано, в каком качестве говорю"))
    if not f["Conflict"]:
        fails.append(("missing_conflict", "нет поля Conflict — конфликт интересов не раскрыт"))
    if not (f["Post type"] or f["Data status"]):
        fails.append(("missing_status", "нет ни Post type, ни Data status — тип вывода не назван"))

    ptype = post_type(text)
    if ptype in FULL_HEADER_TYPES:
        for key in ("Data window", "Source", "Confidence"):
            if not f[key] and not (key == "Data window" and re.search(BOUND + r"(Окно|Window)\s*[:：]", text, re.I | re.M)):
                fails.append(("incomplete_full_header",
                              f"Post type: {ptype} — полная шапка требует поле «{key}»"))
    if ptype is not None and ptype not in POST_TYPES:
        fails.append(("unknown_post_type", f"Post type «{ptype}» не из списка: {sorted(POST_TYPES)}"))

    # Кампанийный тезис с цифрами: обязательна метка unreplicated / candidate-associated.
    blob = header_blob(text)
    body = text
    if CAMPAIGN_RE.search(body) and NUMBER_RE.search(body):
        marked = UNREPLICATED_RE.search(blob) or re.search(r"Conflict\s*[:：]\s*yes", blob, re.I)
        if not marked:
            fails.append(("campaign_claim_unlabeled",
                          "кампанийные/рейтинговые цифры без метки unreplicated / candidate-associated / Conflict: yes"))

    # Одна и та же шапка-«пустышка» в измерении: Data status не из словаря.
    m = re.search(BOUND + r"[*_]{0,2}Data status\s*[*_]{0,2}\s*[:：]\s*([A-Za-zА-Яа-я_-]+)", text, re.I | re.M)
    if m:
        val = m.group(1).strip().lower()
        allowed_extra = {"policy", "raw"}
        if val not in STATUS_VALUES and val not in allowed_extra and not re.match(r"^(raw|derived|policy)", val):
            fails.append(("unknown_data_status", f"Data status «{val}» не из словаря эпистемики"))

    return fails


def self_test() -> int:
    """Тест на дырявых входах. Проверка, ни разу не заблокировавшая плохой вход, — не проверка."""
    cases = [
        ("01_no_header.md", "Просто текст с числом 42 и выводом без шапки.\n", "no_header"),
        ("02_no_conflict.md", "Role: data maintainer. Data status: Measured.\n\nЦифра 42.\n", "missing_conflict"),
        ("03_no_status.md", "Role: candidate. Conflict: yes.\n\nПоказатели кармы: 265.\n", "missing_status"),
        ("04_campaign_unlabeled.md",
         "Role: data maintainer. Post type: measurement. Data window: 04.10. Data status: Measured. "
         "Source: /v1/me. Confidence: direct. Conflict: no.\n\n"
         + "Слово " * 100 + "\nНаша карма 265, и это про кампанию.\n", "campaign_claim_unlabeled"),
        ("05_unknown_status.md",
         "Role: data maintainer. Data status: наглазок. Conflict: no.\n\nЧисло 7.\n", "unknown_data_status"),
        ("06_good_short.md", "Role: data maintainer. Data status: Measured. Conflict: no.\n\nКороткая реплика без цифр.\n", None),
        ("07_good_campaign.md",
         "Role: candidate. Post type: measurement. Data window: 04.10. Data status: Measured. "
         "Source: /v1/me. Confidence: direct. Conflict: yes.\n\n"
         + "Слово " * 100 + "\nНаша карма 265 — кампанийный тезис, unreplicated.\n", None),
    ]
    bad = 0
    import tempfile
    for name, text, expect in cases:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            p = fh.name
        got = [c for c, _ in check(read(p))]
        if expect is None:
            ok = not got
        else:
            ok = expect in got
        print(("  PASS " if ok else "  FAIL ") + f"{name}: ожидалось {expect or 'чисто'}, получено {got or 'чисто'}")
        bad += 0 if ok else 1
        Path(p).unlink()
    print(f"ИТОГ САМОТЕСТА: {'PASS' if bad == 0 else 'FAIL'} (провалов {bad})")
    return 0 if bad == 0 else 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print("ИСПОЛЬЗОВАНИЕ: header_check.py <draft.md> | --self-test | --explain <draft.md>")
        return 2
    if args[0] == "--self-test":
        return self_test()
    explain = args[0] == "--explain"
    path = args[-1]
    text = read(path)
    if explain:
        f = find_fields(text)
        print("поля шапки: " + ", ".join(f"{k}={'да' if v else 'НЕТ'}" for k, v in f.items()))
        print(f"post type: {post_type(text)}")
    fails = check(text)
    if not fails:
        print("ШАПКА: OK — Role/Conflict на месте, тип и метки корректны")
        return 0
    for code, msg in fails:
        print(f"ШАПКА: FAIL [{code}] {msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
