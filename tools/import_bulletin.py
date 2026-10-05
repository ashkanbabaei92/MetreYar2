#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""واردکردنِ شاخص‌های قطعیِ یک بخشنامهٔ جدید — فاز E-9 §۶.

این ابزار شاخص‌های استخراج‌شده از یک بخشنامهٔ جدید (مثلاً شاخص قطعیِ
سه‌ماههٔ اول ۱۴۰۵) را می‌گیرد، اعتبارسنجی می‌کند، اثرش را روی پروژهٔ مرجع
گزارش می‌دهد، و در صورتِ تایید در `config/index_bulletins.json` می‌نویسد.

اعتبارسنجی‌ها:
  ۱) **تکرار (duplicate):** شمارهٔ بخشنامه قبلاً وارد شده → خطا (با --force
     قابلِ رد).
  ۲) **پرشِ >۳۰٪:** هر مقداری که نسبت به دورهٔ قبلش بیش از ۳۰٪ تغییر
     کرده → هشدار (احتمالِ خطای استخراج/تایپ).
  ۳) **سه‌ماههٔ غایب (missing season):** ردیفی که مقدارِ سه‌ماهه را ندارد،
     یا سه‌ماهه/نوعِ نامعتبر → خطا.

گزارشِ اثر: ΔP (موتورِ تعدیل) و برآوردِ به‌هنگام (q4 و ۱۴۰۵Q1) قبل و بعد
از واردکردن، روی پروژهٔ مرجع.

استفاده:
  python tools/import_bulletin.py --input q1_1405.json              # خشک
  python tools/import_bulletin.py --input q1_1405.json --apply      # نوشتن
  python tools/import_bulletin.py --sample > q1_1405.json           # قالب

ورودی: یک پروندهٔ JSON با این شکل (مقادیرِ نمونه — جایگزین کنید):

  {
    "bulletin": "بخشنامه ۱۴۰۵/۱۴۵۶۷۸",
    "bulletin_date": "۱۴۰۵/۰۷/۰۱",
    "title": "شاخص‌های قطعی تعدیل آحادبها — سه‌ماهه اول ۱۴۰۵",
    "annex": "پیوست ۳",
    "source_file": "tadil-1405q1.pdf",
    "entered_by": "نام شما",
    "quarter": "1405Q1",
    "kind": "disciplines",
    "rows": [
      {"name": "ابنیه", "q1_1405": 16500.0, "page": 4}
    ]
  }

`kind` یا `disciplines` است (جدولِ رشته‌ها) یا `chapters_abnieh` (جدولِ
فصل‌ها — آن‌گاه هر ردیف `chapter` عددی می‌خواهد). `quarter` یکی از
۱۴۰۵Q1..۱۴۰۵Q4 است.

قاعدهٔ طلایی: هیچ عددی حدس زده نمی‌شود. ابزار فقط مقادیری را می‌نویسد که
شما داده‌اید، و تا `announced=true` و حداقل یک ردیف وارد نشود، موتورها
از شاخصِ موقت استفاده می‌کنند (فاز E-9 §۳.۶).
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

CONFIG_PATH = os.path.join(ROOT, "config", "index_bulletins.json")

# ── ثابت‌ها ──

QUARTER_FIELD = {"1405Q1": "q1_1405", "1405Q2": "q2_1405",
                 "1405Q3": "q3_1405", "1405Q4": "q4_1405"}
QUARTER_LABEL = {"1405Q1": "سه‌ماهه اول ۱۴۰۵", "1405Q2": "سه‌ماهه دوم ۱۴۰۵",
                 "1405Q3": "سه‌ماهه سوم ۱۴۰۵", "1405Q4": "سه‌ماهه چهارم ۱۴۰۵"}
# ترتیبِ دوره‌ها برای پیداکردنِ «دورهٔ قبل» در بررسیِ پرش.
PERIOD_ORDER = ["base_esfand_1403", "q1_1404", "q2_1404", "q3_1404", "q4_1404",
                "q1_1405", "q2_1405", "q3_1405", "q4_1405"]
JUMP_THRESHOLD = 0.30
KINDS = ("disciplines", "chapters_abnieh")

# تنظیماتِ پروژهٔ مرجع (آینهٔ tests/char_python/test_T117_decision_impact.py).
PROV_COEF = 1.1530518586507572  # [REF] — ضریب موقت ۱۴۰۵Q1 (§۳.۲)
BASE = dict(tadil_enabled=True, tadil_approved=True,
            proposal_date="۱۴۰۳/۱۲/۲۹",
            baravord_enabled=True, baravord_approved=True,
            work_period_start="۱۴۰۴/۰۱/۰۱", work_period_end="۱۴۰۵/۰۲/۱۵",
            provisional_coef_1405q1=PROV_COEF)

_FA_DIGITS = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")


def fa(x, nd=2):
    """عدد به فارسی با جداکنندهٔ هزارگان."""
    try:
        return f"{float(x):,.{nd}f}".translate(_FA_DIGITS)
    except (TypeError, ValueError):
        return str(x)


def fa_pct(x, nd=1):
    """درصدِ امضا‌دار به فارسی (مثلاً ۴۰٫۰٪)."""
    return ("%+.*f" % (nd, float(x) * 100.0)).translate(_FA_DIGITS) + "٪"


def fa_sign(x, nd=2):
    """مبلغِ ریال با علامتِ صریحِ مثبت/منفی."""
    try:
        return f"{float(x):+,.{nd}f}".translate(_FA_DIGITS)
    except (TypeError, ValueError):
        return str(x)


# ═════════_normalization ─════════

_DIGIT_RUN = re.compile(r"[0-9۰-۹٠-٩]+")


def _to_fa_digits(s):
    return (s.translate(str.maketrans("٠-٩0-9", "۰-۹۰-۹"))
            if isinstance(s, str) else str(s))


def bulletin_key(raw):
    """کلیدِ قابلِ مقایسه برای شمارهٔ بخشنامه: طولانی‌ترین رشتهٔ رقم.

    مثلاً «بخشنامه ۱۴۰۵/۱۵۵۲۳۳» → «۱۵۵۲۳۳» (۱۴۰۵ در همهٔ بخشنامه‌ها
    تکرار می‌شود و نباید مبنایِ تشخیصِ تکرار باشد).
    """
    if not raw:
        return ""
    runs = [_to_fa_digits(r) for r in _DIGIT_RUN.findall(str(raw))]
    return max(runs, key=len) if runs else ""


def existing_bulletin_keys(cfg):
    """همهٔ شمارهٔ بخشنامه‌های ثبت‌شده در config."""
    out = set()
    out.add(bulletin_key((cfg.get("meta") or {}).get("bulletin")))
    for _k, v in (cfg.get("index_sources") or {}).get("periods", {}).items():
        out.add(bulletin_key(v.get("bulletin_no")))
    d1405 = cfg.get("definitive_1405") or {}
    out.add(bulletin_key(d1405.get("source")))
    for _q, v in (d1405.get("quarters") or {}).items():
        out.add(bulletin_key(v.get("source")))
    for e in d1405.get("import_log") or []:
        out.add(bulletin_key(e.get("bulletin")))
    out.discard("")
    return out


# ═════════ اعتبارسنجی ─═════════

def _row_id(row, kind):
    if kind == "disciplines":
        return "رشتهٔ %r" % row.get("name")
    return "فصلِ %s" % row.get("chapter")


def _known_rows(cfg, kind):
    """ردیف‌های شناخته‌شده (از بخشنامهٔ ۱۵۵۲۳۳ + واردشدنی‌های قبلی)."""
    d1405 = cfg.get("definitive_1405") or {}
    src = cfg.get(kind) or []
    known = {}
    for r in src:
        if r.get("is_discipline_summary"):  # ردیفِ خلاصهٔ رشته، نه فصل
            continue
        if kind == "disciplines":
            known[r.get("name")] = r
        else:
            known[str(r.get("chapter"))] = r
    for r in d1405.get(kind) or []:
        if r.get("is_discipline_summary"):
            continue
        if kind == "disciplines":
            known.setdefault(r.get("name"), r)
        else:
            known.setdefault(str(r.get("chapter")), r)
    return known


def _previous_value(cfg, kind, row, field):
    """مقدارِ دورهٔ قبلِ این ردیف (برای بررسیِ پرش)."""
    d1405 = cfg.get("definitive_1405") or {}
    pool = (d1405.get(kind) or []) + (cfg.get(kind) or [])
    ident = (row.get("name") if kind == "disciplines"
             else str(row.get("chapter")))
    idx = PERIOD_ORDER.index(field)
    for prev_key in reversed(PERIOD_ORDER[:idx]):
        for r in pool:
            rid = (r.get("name") if kind == "disciplines"
                   else str(r.get("chapter")))
            if rid == ident and isinstance(r.get(prev_key), (int, float)):
                return float(r[prev_key]), prev_key
    return None, None


def validate(data, cfg):
    """اعتبارسنجیِ ورودی. → (errors, warnings)."""
    errs, warns = [], []

    # ── ساختار ──
    for k in ("bulletin", "bulletin_date", "quarter", "kind", "rows"):
        if not data.get(k):
            errs.append("فیلدِ الزامیِ %r خالی است." % k)
    if errs:
        return errs, warns
    quarter = str(data["quarter"]).strip()
    kind = str(data["kind"]).strip()
    if quarter not in QUARTER_FIELD:
        errs.append("سه‌ماههٔ نامعتبر: %r (معتبرها: %s)"
                    % (quarter, "، ".join(sorted(QUARTER_FIELD))))
    if kind not in KINDS:
        errs.append("نوعِ نامعتبر: %r (معتبرها: %s)" % (kind, "، ".join(KINDS)))
    if not isinstance(data["rows"], list) or not data["rows"]:
        errs.append("فهرستِ rows خالی است.")
    if errs:
        return errs, warns

    field = QUARTER_FIELD[quarter]

    # ── ۱) تکرار ──
    key = bulletin_key(data["bulletin"])
    existing = existing_bulletin_keys(cfg)
    if key and key in existing:
        errs.append("تکرار: بخشنامهٔ %s (کلیدِ %s) قبلاً در config ثبت شده. "
                    "اگر بازنویسیِ عمدی است، --force بزنید."
                    % (data["bulletin"], key))

    # ── ۳) سه‌ماههٔ غایب + نوعِ ردیف ──
    seen_ids = []
    for i, row in enumerate(data["rows"]):
        if not isinstance(row, dict):
            errs.append("ردیفِ %d: یک شیء JSON نیست." % (i + 1))
            continue
        if kind == "disciplines":
            if not row.get("name"):
                errs.append("ردیفِ %d: name خالی است." % (i + 1))
        else:
            ch = row.get("chapter")
            try:
                int(ch)
            except (TypeError, ValueError):
                errs.append("ردیفِ %d: chapter عددی نیست (%r)." % (i + 1, ch))
                continue
        v = row.get(field)
        if not isinstance(v, (int, float)):
            errs.append("سه‌ماههٔ غایب: %s مقدارِ %s را ندارد "
                        "(ردیفِ %d: %s)."
                        % (quarter, field, i + 1, _row_id(row, kind)))
            continue
        if not (v > 0):
            errs.append("مقدارِ نامعتبر: %s = %s (باید مثبت باشد) — %s."
                        % (field, fa(v), _row_id(row, kind)))
            continue
        seen_ids.append(row.get("name") if kind == "disciplines"
                        else str(row.get("chapter")))

        # ── ۲) پرشِ >۳۰٪ ──
        prev, prev_key = _previous_value(cfg, kind, row, field)
        if prev and prev > 0:
            jump = float(v) / prev - 1.0
            if abs(jump) > JUMP_THRESHOLD:
                warns.append(
                    "پرشِ بزرگ: %s از %s (%s) به %s (%s) یعنی %s — "
                    "خطای استخراج/تایپ را بررسی کنید."
                    % (_row_id(row, kind), fa(prev), prev_key, fa(v), field,
                       fa_pct(jump)))

    # ── کامل‌بودن در برابرِ ردیف‌های شناخته‌شده ──
    known = _known_rows(cfg, kind)
    missing = [k for k in known if k not in seen_ids]
    if missing:
        warns.append("تام‌بودن: %d از %d ردیفِ شناخته‌شده وارد شد؛ "
                     "%d ردیف غایب: %s"
                     % (len(seen_ids), len(known), len(missing),
                        "، ".join(str(m) for m in missing[:8])
                        + ("…" if len(missing) > 8 else "")))
    return errs, warns


# ═════════ اعمال به config ─════════

def build_patched(cfg, data):
    """یک کپی از config با واردکردنِ اعمال‌شده (نوشته نمی‌شود)."""
    out = copy.deepcopy(cfg)
    quarter = str(data["quarter"]).strip()
    kind = str(data["kind"]).strip()
    field = QUARTER_FIELD[quarter]
    d = out.setdefault("definitive_1405", {})
    d.setdefault("quarters", {})
    rows = d.setdefault(kind, [])

    ident_key = "name" if kind == "disciplines" else "chapter"
    index = {}
    for r in rows:
        index[str(r.get(ident_key))] = r
    for row in data["rows"]:
        rid = row.get(ident_key)
        if kind == "chapters_abnieh":
            rid = int(rid)
        r = index.get(str(rid))
        if r is None:
            r = dict(row)
            rows.append(r)
            index[str(rid)] = r
        else:
            for k in ("page",):
                if k in row:
                    r[k] = row[k]
            r[field] = row[field]

    d["quarters"][quarter] = {
        "announced": True,
        "source": "%s (%s)" % (data["bulletin"], data.get("annex") or "پیوست ۳"),
        "entry_date": data.get("bulletin_date") or "",
    }
    d["title"] = data.get("title") or d.get("title") or \
        "شاخص‌های قطعی تعدیل آحادبها — %s" % QUARTER_LABEL[quarter]
    d["status"] = "واردشده — %s" % data["bulletin"]
    d["source"] = data["bulletin"]
    d["entry_date"] = data.get("bulletin_date") or ""
    d["entered_by"] = data.get("entered_by") or ""

    # ── ثبتِ منشأ در index_sources (فاز E-9 §۳.۵) ──
    srcs = out.setdefault("index_sources", {}).setdefault("periods", {})
    srcs[field] = {
        "type": "قطعی",
        "bulletin_no": bulletin_key(data["bulletin"]),
        "date": data.get("bulletin_date") or "",
        "annex": data.get("annex") or "پیوست ۳",
        "pages": "—",
        "applies_to": [kind],
        "label": QUARTER_LABEL[quarter],
    }

    # ── گزارشِ واردکردن (مبنایِ بررسیِ تکرار در آینده) ──
    log = d.setdefault("import_log", [])
    log.append({"bulletin": data["bulletin"],
                "bulletin_date": data.get("bulletin_date") or "",
                "quarter": quarter, "kind": kind,
                "field": field, "rows": len(data["rows"]),
                "source_file": data.get("source_file") or "",
                "entered_by": data.get("entered_by") or ""})
    return out


def write_config(path, cfg):
    """نوشتنِ config با حفظِ قالبِ پرونده (CRLF، indent=2، بدون BOM)."""
    text = json.dumps(cfg, ensure_ascii=False, indent=2)
    data = text.replace("\n", "\r\n").encode("utf-8")
    if not data.endswith(b"\r\n"):
        data += b"\r\n"
    with open(path, "wb") as fh:
        fh.write(data)


# ═════════ گزارشِ اثر ─═════════

def _load_reference_inputs():
    revit_dir = os.path.join(ROOT, "data", "export revit")
    dynamo_dir = os.path.join(ROOT, "data", "dynamo")
    if not os.path.isdir(revit_dir) or not os.path.isdir(dynamo_dir):
        return None
    from app import (DynamoMappingParser, RevitScheduleParser)
    tables = []
    for fn in sorted(os.listdir(revit_dir)):
        if fn.endswith(".txt"):
            with open(os.path.join(revit_dir, fn), "r",
                      encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fn, fh.read()))
    maps = []
    for root, _d, fnames in os.walk(dynamo_dir):
        for fn in sorted(fnames):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    maps.append(DynamoMappingParser.auto_detect_and_parse(
                        fh.read(), fn))
    return tables, DynamoMappingParser.merge_formats(maps)


_REF_CACHE = []


def _reference_available():
    return (os.path.isdir(os.path.join(ROOT, "data", "export revit"))
            and os.path.isdir(os.path.join(ROOT, "data", "dynamo")))


def run_reference(index_bulletins, baravord_it_period):
    """اجرای خطِ لولهٔ پروژهٔ مرجع با configِ شاخصِ داده‌شده."""
    import app
    from app import (TechnicalOfficeEngine, _default_fehrest_db,
                     default_settings)
    if not _REF_CACHE:
        got = _load_reference_inputs()
        if got is None:
            return None
        _REF_CACHE.append(got)
    tables_maps = _REF_CACHE[0]
    old = app.INDEX_BULLETINS
    app.INDEX_BULLETINS = index_bulletins
    try:
        s = default_settings()
        s.update(BASE)
        s["baravord_it_period"] = baravord_it_period
        res = TechnicalOfficeEngine(
            _default_fehrest_db(), s).compute(*tables_maps)
        return res
    finally:
        app.INDEX_BULLETINS = old


def _metrics(res):
    t = (res.get("adjustment") or {}).get("tadil") or {}
    b = (res.get("adjustment") or {}).get("baravord") or {}
    if t.get("error") or b.get("error"):
        return None
    return {"dp": float(t.get("delta_p") or 0.0),
            "baravord": float(b.get("result_amount") or 0.0)}


def impact_report(cfg_before, cfg_after):
    """گزارشِ اثر روی ΔP و برآوردِ پروژهٔ مرجع. → لیستِ خطوط."""
    out = []
    if not _reference_available():
        return ["  (دادهٔ پروژهٔ مرجع یافت نشد — گزارشِ اثر رد شد)"]
    out.append("  اثر روی پروژهٔ مرجع [REF]:")
    for label, it in (("برآورد به‌هنگام (It = ۱۴۰۴Q4، قطعی)", "q4"),
                      ("برآورد به‌هنگام (It = ۱۴۰۵Q1)", "1405Q1")):
        before = run_reference(cfg_before, it)
        after = run_reference(cfg_after, it)
        mb, ma = _metrics(before), _metrics(after)
        if mb is None or ma is None:
            out.append("    %s: موتور خطا داد — بررسیِ دستی لازم." % label)
            continue
        out.append("    %s:" % label)
        out.append("      برآورد: %s → %s  (اختلاف %s)"
                   % (fa(mb["baravord"]), fa(ma["baravord"]),
                      fa_sign(ma["baravord"] - mb["baravord"])))
        if it == "q4":
            out.append("      ΔP تعدیل: %s → %s  (اختلاف %s)"
                       % (fa(mb["dp"]), fa(ma["dp"]),
                          fa_sign(ma["dp"] - mb["dp"])))
        else:
            out.append("      توجه: بعد از واردکردن، موتور به‌جای ضریبِ "
                       "موقت (%s) خودِ شاخصِ قطعی را به‌کار می‌برد (§۳.۶)."
                       % fa(PROV_COEF))
    return out


# ═════════ CLI ─═════════

SAMPLE = {
    "bulletin": "بخشنامه ۱۴۰۵/۱۴۵۶۷۸",
    "bulletin_date": "۱۴۰۵/۰۷/۰۱",
    "title": "شاخص‌های قطعی تعدیل آحادبها — سه‌ماهه اول ۱۴۰۵",
    "annex": "پیوست ۳",
    "source_file": "tadil-1405q1.pdf",
    "entered_by": "نام شما",
    "quarter": "1405Q1",
    "kind": "disciplines",
    "rows": [
        {"name": "ابنیه", "q1_1405": 0.0, "page": 4},
    ],
}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="واردکردنِ شاخص‌های قطعیِ یک بخشنامهٔ جدید "
                   "(فاز E-9 §۶)")
    ap.add_argument("--input", help="پروندهٔ JSONِ شاخص‌های جدید")
    ap.add_argument("--config", default=CONFIG_PATH,
                    help="مسیرِ config (پیش‌فرض: config/index_bulletins.json)")
    ap.add_argument("--apply", action="store_true",
                    help="نوشتن در config (بدونِ آن فقط اعتبارسنجی + گزارش)")
    ap.add_argument("--force", action="store_true",
                    help="ردکردنِ خطایِ تکرارِ بخشنامه")
    ap.add_argument("--no-impact", action="store_true",
                    help="بدونِ گزارشِ اثر (سریع‌تر)")
    ap.add_argument("--sample", action="store_true",
                    help="چاپِ یک قالبِ JSONِ خالی و خروج")
    args = ap.parse_args(argv)

    if args.sample:
        print(json.dumps(SAMPLE, ensure_ascii=False, indent=1))
        return 0
    if not args.input:
        ap.error("--input لازم است (یا --sample).")

    with open(args.input, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            print("خطا: JSONِ ورودی نامعتبر است — %s" % exc)
            return 1
    if not isinstance(data, dict):
        print("خطا: ریشهٔ JSON باید یک شیء باشد.")
        return 1

    with open(args.config, "rb") as fh:
        cfg = json.loads(fh.read().decode("utf-8"))

    errs, warns = validate(data, cfg)
    if errs:
        # خطایِ تکرار با --force رد می‌شود
        if args.force:
            dup = [e for e in errs if e.startswith("تکرار:")]
            rest = [e for e in errs if not e.startswith("تکرار:")]
            if rest:
                print("خطاها (حتی با --force):")
                for e in rest:
                    print("  ✗ " + e)
                return 1
            print("هشدار: خطایِ تکرار با --force رد شد:")
            for e in dup:
                print("  ⚠ " + e)
        else:
            print("خطاها:")
            for e in errs:
                print("  ✗ " + e)
            print("\nوردی تصحیح کنید یا در صورتِ عمدی بودن --force بزنید.")
            return 1
    if warns:
        print("هشدارها:")
        for w in warns:
            print("  ⚠ " + w)

    quarter = str(data["quarter"]).strip()
    kind = str(data["kind"]).strip()
    field = QUARTER_FIELD[quarter]
    print("\nگزارشِ واردکردن:")
    print("  بخشنامه: %s (%s)" % (data["bulletin"], data.get("bulletin_date")))
    print("  هدف: definitive_1405 › %s › %s (%s)"
          % (kind, quarter, field))
    print("  ردیف‌ها: %d" % len(data["rows"]))
    print("  بررسیِ پرش: آستانهٔ %s" % fa_pct(JUMP_THRESHOLD, 0))
    if kind == "disciplines":
        print("  دامنهٔ اثر: مسیرِ «گروهی» (پیش‌فرض) از شاخصِ **فصل‌ها** "
              "استفاده می‌کند؛ واردکردنِ **رشته‌ها** فقط روی تجهیز/برچیدن "
              "و مسیرِ «رشته‌ای» اثر می‌گذارد. برای اثر روی ΔP و برآوردِ "
              "کلی، فصل‌ها را هم وارد کنید (kind=chapters_abnieh).")
    else:
        print("  دامنهٔ اثر: شاخصِ **فصل‌ها** روی ΔP و برآورد در مسیرِ "
              "«گروهی» اثر می‌گذارد.")

    patched = build_patched(cfg, data)
    if not args.no_impact:
        print()
        for line in impact_report(cfg, patched):
            print(line)

    if not args.apply:
        print("\nحالتِ خشک: چیزی نوشته نشد. برای نوشتن --apply بزنید.")
        return 0

    write_config(args.config, patched)
    print("\nنوشته شد: %s" % args.config)
    print("  quarters[%s].announced = true  →  موتورها از این پس شاخصِ "
          "قطعی را به‌کار می‌برند (§۳.۶)." % quarter)
    print("  یادآوری: پس از واردکردن، میزانِ تطبیق را با "
          "tools/verify_bulletins.py بررسی کنید.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
