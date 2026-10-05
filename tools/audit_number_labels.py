# -*- coding: utf-8 -*-
"""tools/audit_number_labels.py — فاز E-9 §۲.

ممیزیِ منشأ اعداد: هر عددِ پولی یا شاخص در مستندات باید یک برچسبِ منشأ
داشته باشد:

  [REF]                — پروژهٔ مرجع (دیسپلین ابنیه)
  [FIX]                — fixture آزمون (سناریوی مصنوعی)
  [SRC: شماره بخشنامه, صفحه] — منبعِ رسمی

برچسب‌ها به دو شکل پذیرفته می‌شوند:
  ۱. در خط: `[REF] **۲۳٬۲۱۸٬۳۸۱٬۳۳۷٫۰۱ ریال**`
  ۲. محدوده (نامرئی در رندر): `<!-- labels: [REF] -->` قبل از یک جدول/
     پاراگراف — همهٔ اعدادِ تا سرِ عنوانِ بعدی یا نشانگرِ بعدی را پوشش
     می‌دهد.

اجرا:  python tools/audit_number_labels.py [--fix]
خروجی: فهرستِ اعدادِ بدونِ برچسب + کدِ خروج (۰ = همه برچسب‌دار).
"""
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

# مستنداتی که ممیزی می‌شوند
DOCS = [
    "ACCEPTANCE.md",
    "ARCHITECTURE.md",
    "CHANGELOG.md",
    "README.md",
    "docs/USER_GUIDE.md",
    "docs/PENDING_DECISIONS.md",
    "docs/DECISION_SHEET.md",
    "docs/DECISION_IMPACT.md",
    "docs/DATA_REQUEST.md",
]

LABEL = r"\[(?:REF|FIX|SRC:[^\]]+)\]"
SCOPE_RE = re.compile(r"<!--\s*labels?:\s*((?:%s)(?:\s*,\s*%s)*)\s*-->" % (LABEL, LABEL))
DEFAULT_RE = re.compile(r"<!--\s*default-label:\s*(%s)\s*-->" % LABEL)
INLINE_RE = re.compile(LABEL)

# ── مقادیرِ شاخص از config/index_bulletins.json (دقتِ بدونِ مثبتِ کاذب) ──
def _load_index_values():
    import json
    p = os.path.join(ROOT, "config", "index_bulletins.json")
    vals = set()
    if not os.path.exists(p):
        return vals
    with open(p, encoding="utf-8-sig") as fh:
        data = json.load(fh)

    def walk(v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if 10 <= abs(v) <= 1e7:
                vals.add(round(float(v), 4))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    walk(data)
    return vals

INDEX_VALUES = None

# عددِ پولیِ فارسی با جداکنندهٔ هزارگان
FA_MONEY = re.compile(r"[۰-۹0-9]+(?:٬[۰-۹0-9]{3})+(?:٫[۰-۹0-9]+)?")
# عددِ پولیِ لاتین در فرم کد (مثل 9984277408.22 یا 45_437_742_820.32)
LAT_MONEY = re.compile(r"\b\d[\d_]{6,}\.\d+\b")
# عددِ پولیِ لاتین با کاما (مثل 8,990,157,253.69)
LAT_COMMA = re.compile(r"\b\d{1,3}(?:,\d{3})+\.\d+\b")
# مبلغ با کلمه: ۲٫۵ میلیارد / 252 میلیون / 13.52e9
WORD_MONEY = re.compile(r"\b\d[\d۰-۹.]*\s*(?:میلیارد|میلیون)\b")
SCI_MONEY = re.compile(r"\b\d[\d.]*e\d+\b", re.IGNORECASE)

# چیزهایی که عددِ پولی/شاخص نیستند و باید نادیده گرفته شوند
SKIP_RE = re.compile(r"[%٪]|\d{2,4}/\d{1,2}/\d{1,2}|Q[1-4]")

HEADING_RE = re.compile(r"^#{1,6}\s")
CODE_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_+-]*\s*$")


def _is_index(num_str):
    global INDEX_VALUES
    if INDEX_VALUES is None:
        INDEX_VALUES = _load_index_values()
    if not re.search(r"[٫.]", num_str):
        return False
    try:
        v = float(num_str.replace("٬", "").replace("٫", "."))
    except ValueError:
        return False
    if v < 500:            # شاخص‌های رسمی همگی ≥ ۵۰۰ هستند
        return False
    for cand in INDEX_VALUES:
        if abs(cand - v) < 0.05:
            return True
    return False


def find_numbers(line):
    """تعدادِ اعدادِ پولی/شاخص در یک خط."""
    hits = []
    for rx, kind in ((FA_MONEY, "money"), (LAT_MONEY, "money"),
                     (LAT_COMMA, "money"), (WORD_MONEY, "money"),
                     (SCI_MONEY, "money")):
        for m in rx.finditer(line):
            frag = line[max(0, m.start() - 12):m.end() + 4]
            if SKIP_RE.search(frag):
                continue
            hits.append((kind, m.group()))
    # شاخص: فقط مقادیرِ ثبت‌شده در config
    for m in re.finditer(r"[۰-۹0-9]+[٫.][۰-۹0-9]?", line):
        frag = line[max(0, m.start() - 12):m.end() + 4]
        if SKIP_RE.search(frag):
            continue
        if _is_index(m.group()):
            hits.append(("index", m.group()))
    # حذفِ هم‌پوشانیِ ساده (money بر index اولویت دارد)
    cleaned = []
    for kind, num in hits:
        if kind == "index" and any(k == "money" and n == num for k, n in hits):
            continue
        cleaned.append((kind, num))
    return cleaned


def audit(path):
    """یک سند را ممیزی می‌کند؛ برمی‌گرداند: (تعدادِ کل، فهرستِ بدون برچسب)."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    scope = None
    scope_level = 0
    default_scope = None
    in_code = False
    total = 0
    unlabeled = []
    cur_level = 0
    for lineno, raw in enumerate(lines, 1):
        line = raw.rstrip("\n")
        if CODE_FENCE_RE.match(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        if HEADING_RE.match(line):
            cur_level = len(HEADING_RE.match(line).group(0)) - 1
            if scope is not None and cur_level <= scope_level:
                scope = None
            continue
        m = DEFAULT_RE.search(line)
        if m:
            default_scope = [m.group(1)]
            continue
        m = SCOPE_RE.search(line)
        if m:
            scope = [x.strip() for x in INLINE_RE.findall(m.group(1))]
            scope_level = cur_level
            continue
        for kind, num in find_numbers(line):
            total += 1
            if INLINE_RE.search(line):
                continue
            if scope or default_scope:
                continue
            unlabeled.append((lineno, kind, num, line.strip()[:100]))
    return total, unlabeled


def main():
    fix_mode = "--fix" in sys.argv
    bad = 0
    total_all = 0
    report = []
    for rel in DOCS:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            report.append("MISSING %s" % rel)
            bad += 1
            continue
        total, unl = audit(p)
        total_all += total
        status = "OK  " if not unl else "FAIL"
        report.append("%s %s — %d عدد، %d بدون برچسب"
                      % (status, rel, total, len(unl)))
        if unl:
            bad += len(unl)
            for lineno, kind, num, text in unl[:12]:
                report.append("    L%d %s %r  | %s" % (lineno, kind, num, text))
            if len(unl) > 12:
                report.append("    ... + %d موردِ دیگر" % (len(unl) - 12))
    out = "\n".join(report)
    print(out)
    print("\nجمع: %d عدد بررسی شد، %d بدون برچسب." % (total_all, bad))
    if bad:
        print("نتیجه: FAIL (اعدادِ بدون برچسب وجود دارند)")
        sys.exit(1)
    print("نتیجه: PASS")


if __name__ == "__main__":
    main()
