#!/usr/bin/env python3
"""Проверка публичного профиля: контур полномочий и типы вкладов.

Зачем: 04.10.2026 добавлены два файла, которые заявляют о нас то, чего раньше
никто не мог проверить — ОБЪЁМ ПОЛНОМОЧИЙ (OPERATIONS.md) и РОЛИ ВКЛАДОВ
(methodology/contribution-roles.md). Файл, который заявляет полномочия, обязан
сам проверяться так же, как число проверяется шлюзом. Иначе получится новый
«документ доверия»: красивый, непроверяемый и опасный тем, что на него сошлются.

Что проверяет:
  1. оба файла существуют и непусты;
  2. в каждом на месте обязательные разделы (по маркерам, а не по названию);
  3. все восемь типов вклада названы, и каждый — со своей строкой таблицы;
  4. контур полномочий отвечает на все девять вопросов из брифа;
  5. ни один публичный файл контура не содержит утечек: ключей, токенов,
     приватных путей, внутренних адресов, почты, имён оператора;
  6. CONTRIBUTING и README ссылаются на оба файла — иначе их никто не найдёт.

Чего НЕ проверяет: соответствует ли наше поведение этому файлу. Это проверяется
только противоречием, найденным в журналах (реестр исправлений, журнал
видимости). Тест — про текст, не про добродетель; так и написано в README.

Код возврата: 0 — всё на месте, 1 — есть провал.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPS = ROOT / "OPERATIONS.md"
ROLES = ROOT / "methodology" / "contribution-roles.md"
CONTRIB = ROOT / "CONTRIBUTING.md"
README = ROOT / "README.md"

fails: list[str] = []
passes: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    (passes if ok else fails).append(name)
    print(f"  {'PASS' if ok else 'ПРОВАЛ'}  {name}" + (f" — {detail}" if detail and not ok else ""))


# 1. файлы существуют и непусты
for f in (OPS, ROLES):
    check(f"файл на месте: {f.relative_to(ROOT)}", f.is_file() and f.stat().st_size > 800,
          "нет файла или он подозрительно мал")

if fails:
    print(f"\nИТОГ: провалов {len(fails)}")
    sys.exit(1)

ops = OPS.read_text(encoding="utf-8")
roles = ROLES.read_text(encoding="utf-8")

# 2. обязательные разделы OPERATIONS.md — девять вопросов брифа
ops_sections = {
    "кто действует и в чьём имени": r"who acts|in whose name",
    "разрешено без подтверждения владельца": r"without operator approval|standing scope",
    "запрещено полностью": r"never, under any circumstance|never",
    "что хранится и как долго": r"retention|for how long",
    "как публикуется исправление": r"correction gets published|correction is published",
    "ручная редактура политических постов": r"manual editing of political posts|pre-publication editorial review",
    "как агента можно остановить": r"can be stopped",
    "кто владеет инфраструктурой": r"owns none of the infrastructure|owner holds|owns the",
    "как это проверить самому": r"check this file instead of believing",
}
for label, pat in ops_sections.items():
    check(f"OPERATIONS.md отвечает: {label}", re.search(pat, ops, re.I) is not None, f"маркер /{pat}/ не найден")

# 3. восемь типов вклада — каждый со своей строкой таблицы
role_types = ["question", "report", "hypothesis", "replication", "critique", "engineering", "curation", "proposal"]
for t in role_types:
    check(f"тип вклада назван: {t}", re.search(r"^\|\s*`" + t + r"`", roles, re.M) is not None,
          "нет строки таблицы для этого типа")

# 4. операционные запреты перечислены поимённо
for ban, pat in {
    "секреты и персональные данные": r"keys, tokens, cookies",
    "публикация без шлюза": r"did not pass the gate",
    "действия от чужого имени": r"as another agent",
    "изменение метода в электоральный период": r"electoral period",
    "смешивание аудита и агитации": r"audit and advocacy",
    "самопиннинг": r"own material|own account",
}.items():
    check(f"запрет назван: {ban}", re.search(pat, ops, re.I) is not None, f"маркер /{pat}/ не найден")

# 5. утечек нет ни в одном публичном файле контура
leak_patterns = {
    "github-токен": r"gh[pousr]_[A-Za-z0-9]{20,}",
    "открытый ключ": r"BEGIN [A-Z ]*PRIVATE KEY",
    "bearer-заголовок со значением": r"[Bb]earer\s+[A-Za-z0-9._\-]{16,}",
    "присвоение токена/пароля": r"(?:token|secret|password|passwd|api[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9._\-]{8,}",
    "приватный путь нашего узла": r"/home/agent|/workspace|/proc/self",
    "внутренний адрес": r"\.svc(?:\.cluster)?\.local|mcp-gateway|v2bot\.svc",
    "электронная почта": r"[\w.+-]+@[\w-]+\.[a-z]{2,}",
    "ip-адрес": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
}
# Упоминание владельца — не то же, что техническая утечка. По схеме `reported_by`
# поле обязано называть автора обнаружения, и однажды им оказался владелец. Но
# публичный репозиторий, читаемый вместе с ником агента на борде, устанавливает
# связь «агент <-> конкретный человек» — а пункт о контуре полномочий требует НЕ
# раскрывать оператора. Это противоречие двух наших же правил, и решает его
# владелец, а не тест. Поэтому категория отдельная: она валит набор и печатается
# как открытый вопрос, пока решение не принято.
OWNER_PATTERNS = r"AnKocrypto|Антон|Antuan"
OWNER_DECISION = "redacted"  # redacted = обезличено 04.10.2026 по решению владельца; allowed = владелец оставил намеренно
public_files = [OPS, ROLES, CONTRIB, README, ROOT / "SCOPE.md", ROOT / "SECURITY.md",
                ROOT / "CONFLICTS.md", ROOT / "contracts" / "POST_HEADER.md",
                ROOT / "contracts" / "ACCOUNTABILITY_CONTRACT_v1.md",
                ROOT / "methodology" / "falsifiers.md",
                ROOT / "ledger" / "CORRECTIONS.md", ROOT / "ledger" / "VISIBILITY.md"]
_present = []
for f in public_files:
    if f.is_file():
        _present.append(f)
    else:
        print(f"  ПРОВАЛ  файл из списка публичных не найден: {f.relative_to(ROOT)}")
        fails.append(f"нет файла {f.relative_to(ROOT)}")
public_files = _present
for f in public_files:
    if not f.is_file():
        check(f"утечки: {f.relative_to(ROOT)}", False, "файл не найден")
        continue
    text = f.read_text(encoding="utf-8", errors="replace")
    hits = [name for name, pat in leak_patterns.items() if re.search(pat, text)]
    check(f"утечки: {f.relative_to(ROOT)}", not hits, f"найдено: {', '.join(hits)}")

# 5b. упоминания владельца — отдельная категория
owner_hits = []
for f in public_files:
    text = f.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(OWNER_PATTERNS, text):
        line = text[:m.start()].count("\n") + 1
        owner_hits.append(f"{f.relative_to(ROOT)}:{line}")
if OWNER_DECISION == "allowed":
    # Владелец решил оставить имя намеренно — проверка становится справкой.
    print(f"  ИНФО  упоминания владельца: решение владельца «allowed», найдено {len(owner_hits)} — это осознанный выбор, не утечка")
else:
    # «open» (вопрос не решён) и «redacted» (обезличено 04.10.2026) — оба строгие.
    # Правка 04.10.2026: раньше ветка redacted печатала ИНФО и тем самым перестала
    # ловить возврат имени. Тест, который после починки перестаёт проверять, — это
    # не тест, а его отчёт о проделанной работе.
    check("упоминания владельца в публичном контуре отсутствуют",
          not owner_hits,
          f"ОТКРЫТЫЙ ВОПРОС ВЛАДЕЛЬЦУ: {len(owner_hits)} упоминаний — {', '.join(owner_hits[:5])}; решить: оставить намеренно или обезличить"
          if OWNER_DECISION == "open" else
          f"ОБЕЗЛИЧЕНО, НО ИМЯ ВЕРНУЛОСЬ: {len(owner_hits)} — {', '.join(owner_hits[:5])}")

# 6. на файлы можно наткнуться — ссылки из CONTRIBUTING и README
for f, name in ((CONTRIB, "CONTRIBUTING.md"), (README, "README.md")):
    t = f.read_text(encoding="utf-8")
    check(f"{name} ссылается на OPERATIONS.md", "OPERATIONS.md" in t)
    check(f"{name} ссылается на типы вкладов", "contribution-roles.md" in t or "contribution roles" in t)

# 7. ручная редактура названа честно, а не спрятана
check("редактура названа отсутствующей, а не умолчана",
      re.search(r"no pre-publication editorial review|There is \*\*no", ops, re.I) is not None,
      "нет прямого признания отсутствия предварительной редактуры")

print(f"\nИТОГ: проверок {len(passes) + len(fails)}, провалов {len(fails)}")
if fails:
    print("ВЕРДИКТ: FAIL — " + "; ".join(fails[:4]))
    sys.exit(1)
print("ВЕРДИКТ: PASS — оба файла на месте, обязательные разделы и запреты названы, утечек нет, ссылки есть")
sys.exit(0)
