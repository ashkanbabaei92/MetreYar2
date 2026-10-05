# -*- coding: utf-8 -*-
"""tools/decision_impact.py — فاز E-9 §۱.

اثرِ واقعیِ هر تصمیمِ باز (D-01..D-20) را روی پروژهٔ مرجع با اجرای موتور
اندازه می‌گیرد. «اثر صفر» فقط با عددِ اجرای واقعی پذیرفته می‌شود.

خروجی‌ها:
  docs/DECISION_IMPACT.md          — جدولِ توضیحی
  docs/decision_impact.csv         — داده‌ها
  tools/decision_impact_scenarios.json — سناریوها (برای تستِ پاریتیِ T117)

اجرا:  python tools/decision_impact.py
"""
import json
import logging
import os
import sys

logging.disable(logging.WARNING)
ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from app import (DynamoMappingParser, RevitScheduleParser, TechnicalOfficeEngine,
                 _default_fehrest_db, default_settings)

REVIT_DIR = os.path.join(ROOT, "data", "export revit")
DYNAMO_DIR = os.path.join(ROOT, "data", "dynamo")

PROV_COEF = 1.1530518586507572

# ── تنظیماتِ پایهٔ پروژهٔ مرجع (آینهٔ T97/T113) ──
BASE = dict(
    tadil_enabled=True,
    tadil_approved=True,
    proposal_date="۱۴۰۳/۱۲/۲۹",
    baravord_enabled=True,
    baravord_approved=True,
    work_period_start="۱۴۰۴/۰۱/۰۱",
    work_period_end="۱۴۰۵/۰۲/۱۵",
    provisional_coef_1405q1=PROV_COEF,
)

# new-item Injection مشترک برای D-14/D-15/D-16
NEW_ITEM_1E9 = dict(new_item_amount=1e9, new_item_base_period="1404Q1")

# kind: setting = فلپِ تنظیمات؛ code = گزینهٔ ب در کد پیاده نشده؛
#       data = نیازمند دادهٔ خارجی؛ special = محاسبهٔ ویژه
SCENARIOS = [
    {"id": "D-01", "kind": "setting",
     "subject": "ضریب k: ۰٫۹۵ یا ۱",
     "a": "۰٫۹۵ موقت → ۱ در قطعی (الان)",
     "b": "۱ از همان ابتدا",
     "flip": {"completed_within_term": True}},
    {"id": "D-02", "kind": "code",
     "subject": "گرانولاریتیِ گردکردن (هر سه‌ماهه یا کل)",
     "a": "هر سه‌ماهه جداگانه (الان)", "b": "گردکردنِ کل"},
    {"id": "D-03", "kind": "setting",
     "subject": "تفسیرِ گردکردن (بند ۸-۲)",
     "a": "گردکردنِ روشن (الان)", "b": "گردکردنِ خاموش",
     "flip": {"coef_rounding_2080": False}},
    {"id": "D-04", "kind": "code",
     "subject": "ضرایبِ منفی",
     "a": "مجازند (الان)", "b": "صفر شدن"},
    {"id": "D-05", "kind": "code",
     "subject": "دقتِ محاسبات (بدون خطای شناور)",
     "a": "حسابِ دقیق (الان)", "b": "گردکردنِ ساده"},
    {"id": "D-06", "kind": "code",
     "subject": "نحوهٔ ورودِ وضعیتِ اتمام (UI)",
     "a": "selectbox (الان)", "b": "فیلدِ عددی k"},
    {"id": "D-07", "kind": "code",
     "subject": "مبنای کسرِ ۵٪",
     "a": "از کلِ ΔP (الان)", "b": "فقط از بخشِ قطعی"},
    {"id": "D-08", "kind": "setting",
     "subject": "کسر در تعدیلِ منفی",
     "a": "خیر + هشدار (الان)", "b": "بله",
     "flip": {"fault_deduction_on_negative": True}},
    {"id": "D-09", "kind": "setting",
     "subject": "گرانولاریتیِ ۲-۶ (سه‌ماهه‌های قطعی‌نشده)",
     "a": "میانگینِ ۲-۶ (الان)", "b": "شاخصِ هر دورهٔ خودش",
     "flip": {"provisional_diff_method": "own_period"}},
    {"id": "D-10", "kind": "setting",
     "subject": "کارِ پوشش‌شده با تمدیدِ مجاز",
     "a": "درونِ مدت + میانگینِ ۲-۶ (الان)",
     "b": "شاخصِ همان دوره",
     "flip": {"contract_extensions": [
         {"date": "۱۴۰۵/۰۲/۱۵", "months": 3, "kind": "مجاز",
          "doc_no": "سناریوی ابزار"}]}},
    {"id": "D-11", "kind": "setting",
     "subject": "آستانهٔ ۳۰۰ میلیون ریال",
     "a": "مقدار از config (الان)",
     "b": "آستانه بالا ⇒ مسیرِ رشته‌ای (همان D-13)",
     "flip": {"index_method": "رشته‌ای"},
     "note": ("در پروژهٔ مرجع grand_total = ۳۱٫۴B > ۳۰۰M است و مسیرِ گروهی "
              "گرفته می‌شود؛ تنها راهِ عددی برای دیدنِ اثر، اجبارِ مسیرِ "
              "رشته‌ای است که دقیقاً با D-13 یکسان است.")},
    {"id": "D-12", "kind": "code",
     "subject": "مرزِ آستانه (دقیقاً برابر)",
     "a": "amount >= threshold ⇒ گروهی (الان)", "b": "رشته‌ای"},
    {"id": "D-13", "kind": "setting",
     "subject": "گرانولاریتیِ مسیرِ رشته‌ای",
     "a": "گروهی (الان)", "b": "رشته‌ای (شاخصِ رشته برای همه)",
     "flip": {"index_method": "رشته‌ای"}},
    {"id": "D-14", "kind": "setting",
     "subject": "تعدیلِ کارِ جدیدِ اضافه‌شده",
     "a": "بله، مثلِ تجهیز تعدیل می‌شود (الان)",
     "b": "فقط جبرانِ ۳-۵ بدونِ تعدیلِ مجدد",
     "flip": dict(NEW_ITEM_1E9, new_item_method="فهرست پیمان"),
     "note": ("اثر = سهمِ کارِ جدیدِ ۱ میلیارد ریالی از ΔP (گزینهٔ ب آن را "
              "حذف می‌کند).")},
    {"id": "D-15", "kind": "setting",
     "subject": "دورهٔ شاخصِ مبنا برای کارِ جدید ناموجود",
     "a": "ردیف ساخته نمی‌شود + خطا (الان)",
     "b": "استفاده از دورهٔ موجود (اینجا 1404Q1)",
     "flip": dict(NEW_ITEM_1E9, new_item_method="قیمت روز"),
     "baseline_flip": dict(new_item_amount=1e9, new_item_base_period="",
                           new_item_method="قیمت روز"),
     "note": ("سناریو در روشِ «قیمت روز» معنا دارد (در «فهرست پیمان» "
              "دوره نادیده گرفته می‌شود).")},
    {"id": "D-16", "kind": "setting",
     "subject": "روشِ کارِ جدید",
     "a": "فهرست پیمان (الان)", "b": "قیمت روز",
     "flip": dict(NEW_ITEM_1E9, new_item_method="قیمت روز"),
     "baseline_flip": dict(NEW_ITEM_1E9, new_item_method="فهرست پیمان"),
     "note": "اثر = تفاوتِ ΔP بین دو روش برای کارِ جدیدِ ۱ میلیارد ریالی."},
    {"id": "D-17", "kind": "code",
     "subject": "گردکردنِ ضریبِ تبدیلِ ۳-۵",
     "a": "گرد نمی‌شود (الان)", "b": "گرد شود"},
    {"id": "D-18", "kind": "special",
     "subject": "مبنای «مبلغ برآورد» در سقفِ ۱۰٪",
     "a": "base_total × ۱٫۱ (الان)", "b": "grand_total × ۱٫۱"},
    {"id": "D-19", "kind": "data",
     "subject": "شاخصِ کلیِ مستقل",
     "a": "شاخصِ رشته (الان)", "b": "شاخصِ کلیِ مرکز آمار"},
    {"id": "D-20", "kind": "data",
     "subject": "مصالحِ پای‌کار",
     "a": "شاخصِ رشته (الان)", "b": "شاخصِ اختصاصی"},
]


def build_inputs():
    tables = []
    for fn in sorted(os.listdir(REVIT_DIR)):
        if fn.endswith(".txt"):
            with open(os.path.join(REVIT_DIR, fn), "r", encoding="utf-8-sig") as fh:
                tables.append(RevitScheduleParser.parse(fn, fh.read()))
    results = []
    for root, _d, fns in os.walk(DYNAMO_DIR):
        for fn in sorted(fns):
            if fn.endswith(".txt"):
                with open(os.path.join(root, fn), "rb") as fh:
                    results.append(
                        DynamoMappingParser.auto_detect_and_parse(fh.read(), fn))
    return tables, DynamoMappingParser.merge_formats(results)


def run(tables, map_df, overrides):
    s = default_settings()
    s.update(BASE)
    s.update(overrides or {})
    r = TechnicalOfficeEngine(_default_fehrest_db(), s).compute(tables, map_df)
    t = (r.get("adjustment") or {}).get("tadil") or {}
    b = (r.get("adjustment") or {}).get("baravord") or {}
    return {
        "base_total": r.get("base_total"),
        "grand_total": r.get("grand_total"),
        "delta_p": t.get("delta_p"),
        "delta_p_definitive": t.get("delta_p_definitive"),
        "baravord": b.get("result_amount"),
    }


def _d(a, b):
    if a is None or b is None:
        return None
    return round(b - a, 2)


def main():
    tables, map_df = build_inputs()
    print("سناریوها اجرا می‌شوند (هر کدام ~۱۲s) ...")

    base_m = run(tables, map_df, {})
    rows = []
    for sc in SCENARIOS:
        row = {"id": sc["id"], "subject": sc["subject"],
               "kind": sc["kind"], "option_a": sc.get("a", ""),
               "option_b": sc.get("b", "")}
        if sc["kind"] == "setting":
            bflip = sc.get("baseline_flip")
            ref = run(tables, map_df, bflip) if bflip else base_m
            m = run(tables, map_df, sc["flip"])
            row.update({k: m[k] for k in
                        ("base_total", "grand_total", "delta_p", "baravord")})
            row["d_delta_p"] = _d(ref["delta_p"], m["delta_p"])
            row["d_baravord"] = _d(ref["baravord"], m["baravord"])
            row["ref_delta_p"] = ref["delta_p"]
            row["measurable"] = True
        elif sc["kind"] == "special" and sc["id"] == "D-18":
            # سقفِ ۱۰٪: مقایسهٔ دو مبنا (عدد ثابت، نه ΔP)
            bt = base_m["base_total"]
            gt = base_m["grand_total"]
            row["ceiling_a"] = round(bt * 1.1, 2)
            row["ceiling_b"] = round(gt * 1.1, 2)
            row["d_ceiling"] = round(gt * 1.1 - bt * 1.1, 2)
            row["measurable"] = True
        else:
            row["measurable"] = False
            row["d_delta_p"] = None
            row["d_baravord"] = None
        row["note"] = sc.get("note", "")
        rows.append(row)
        print("  %s done" % sc["id"])

    # ── خروجیِ JSON سناریوها + اعداد (برای T117) ──
    json_path = os.path.join(os.path.dirname(__file__),
                             "decision_impact_scenarios.json")
    payload = {"base": BASE, "baseline_metrics": base_m,
               "scenarios": SCENARIOS,
               "results": {r["id"]: r for r in rows}}
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    print("نوشته شد: %s" % json_path)

    # ── CSV ──
    import csv
    csv_path = os.path.join(ROOT, "docs", "decision_impact.csv")
    cols = ["id", "subject", "kind", "measurable", "delta_p", "d_delta_p",
            "baravord", "d_baravord", "ceiling_a", "ceiling_b", "d_ceiling",
            "note"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("نوشته شد: %s" % csv_path)

    # ── Markdown ──
    md_path = os.path.join(ROOT, "docs", "DECISION_IMPACT.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown(base_m, rows))
    print("نوشته شد: %s" % md_path)


def fa_num(v, digits=2):
    if v is None:
        return "—"
    neg = "−" if v < 0 else ""
    s = f"{abs(v):,.{digits}f}"
    FA = "۰۱۲۳۴۵۶۷۸۹"
    s = "".join(FA[int(c)] if c.isdigit() else c for c in s)
    return neg + s.replace(",", "٬").replace(".", "٫")


def build_markdown(base_m, rows):
    L = []
    A = L.append
    A("# اثرِ واقعیِ هر تصمیم روی پروژهٔ مرجع — فاز E-9 §۱\n")
    A("<!-- default-label: [REF] -->\n")
    A("هر عدد با **اجرای واقعیِ موتور** روی پروژهٔ مرجع به‌دست آمده است. "
      "«اثر صفر» فقط با اجرا پذیرفته می‌شود.\n")
    A("**تنظیماتِ پایهٔ مرجع** (آینهٔ T97/T113): دورهٔ کاری ۱۴۰۴/۰۱/۰۱ تا "
      "۱۴۰۵/۰۲/۱۵، تاریخِ پیشنهاد ۱۴۰۳/۱۲/۲۹، هر دو موتور فعال، "
      "It = ۱۴۰۴Q4.\n")
    A("**اعدادِ پایه:** base_total = %s، grand_total = %s، ΔP = %s، "
      "برآورد به‌هنگام = %s ریال.\n"
      % (fa_num(base_m["base_total"]), fa_num(base_m["grand_total"]),
         fa_num(base_m["delta_p"]), fa_num(base_m["baravord"])))
    A("\n> **نکتهٔ مهم:** چند ادعای «اثر صفر» در مستنداتِ قبلی با این اجرا "
      "رد شدند (D-03 و D-13). جزئیات در آخرِ این سند.\n")
    A("\n---\n")
    A("## جدولِ اصلی\n")
    A("<!-- labels: [REF], [FIX] -->\n")
    A("دو برچسبِ این جدول: **[REF]** = خروجیِ واقعیِ موتور روی پروژهٔ مرجع،\n"
      "و **[FIX]** = سناریوی تزریق‌شدهٔ ۱ میلیارد ریالیِ کارِ جدید (D-14،\n"
      "D-15، D-16) که عددِ واقعیِ پروژه نیست.\n")
    A("| شناسه | موضوع | گزینهٔ ب | ΔP (ریال) | اثر روی ΔP | برآورد (ریال) | "
      "اثر روی برآورد | قابلِ اندازه‌گیری |")
    A("|---|---|---|---|---|---|---|---|")
    for r in rows:
        if r["kind"] == "special":
            A("| %s | %s | %s | — | — | — | — | بله (ویژه) |"
              % (r["id"], r["subject"], r["option_b"]))
            continue
        if not r["measurable"]:
            why = {"code": "گزینهٔ ب در کد پیاده نشده",
                   "data": "نیازمند دادهٔ خارجی"}.get(r["kind"], "—")
            A("| %s | %s | %s | — | — | — | — | **خیر** (%s) |"
              % (r["id"], r["subject"], r["option_b"], why))
            continue
        A("| %s | %s | %s | %s | **%s** | %s | **%s** | بله |"
              % (r["id"], r["subject"], r["option_b"],
                 fa_num(r.get("delta_p")), fa_num(r.get("d_delta_p")),
                 fa_num(r.get("baravord")), fa_num(r.get("d_baravord"))))
    A("\n---\n")
    A("## سقفِ ۱۰٪ (D-18)\n")
    for r in rows:
        if r["id"] == "D-18":
            A("| مبنا | فرمول | سقف (ریال) |")
            A("|---|---|---|")
            A("| گزینهٔ الف (الان) | base_total × ۱٫۱ | **%s** |"
              % fa_num(r["ceiling_a"]))
            A("| گزینهٔ ب | grand_total × ۱٫۱ | **%s** |"
              % fa_num(r["ceiling_b"]))
            A("| اختلاف | — | **%s** |" % fa_num(r["d_ceiling"]))
    A("\n---\n")
    A("## ردِ ادعاهای «اثر صفر»\n")
    for r in rows:
        if r["measurable"] and r["id"] in ("D-03", "D-13"):
            A("- **%s:** اثر روی ΔP = **%s ریال** و روی برآورد = "
              "**%s ریال** — صفر نیست."
              % (r["id"], fa_num(r.get("d_delta_p")),
                 fa_num(r.get("d_baravord"))))
    A("\n**دلیل:** در مستنداتِ E-6 نوشته شده بود «۰»، چون فکر می‌شد پروژهٔ "
      "مرجع روی مسیر/تنظیمِ پیش‌فرض می‌ماند و کسی گزینهٔ ب را اجرا نمی‌کند. "
      "ولی «اثرِ تصمیم» یعنی عددی که با انتخابِ گزینهٔ ب به‌دست می‌آید — و "
      "این اعداد صفر نیستند.")
    A("\n---\n")
    A("تولیدشده با `tools/decision_impact.py` (فاز E-9 §۱). سناریوها در "
      "`tools/decision_impact_scenarios.json` و تستِ پاریتی T117.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
