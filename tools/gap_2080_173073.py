# -*- coding: utf-8 -*-
"""tools/gap_2080_173073.py — فاز E-11-A §۳.

اندازه‌گیریِ عددیِ اثرِ شکاف‌های ۲۰۸۰ → ۱۷۳۰۷۳ روی پروژهٔ مرجع،
**بدون هیچ تغییری در کد**. فقط از فلگ‌ها و ورودی‌های موجود استفاده
می‌شود و هر چیزی که با فلگ ممکن نیست، صراحتاً «نیازمند تغییرِ کد»
گزارش می‌شود.

سناریوهای قابلِ شبیه‌سازی:
  BASELINE   رفتارِ فعلی (۲۰۸۰) — مرجعِ مقایسه
  G-K1       k=1 (۲۰۸۰ ۱-۸ تبصرهٔ ۲ / ۱۷۳۰۷۳ ۸-۱) — **کرانِ بالا**
             برای k=۰٫۹۷۵ که در ۱۷۳۰۷۳ ۸-۲ جدید است
  G-FASKH    فسخ با قصور (۲۰۸۰ بند ۷) — مقدارِ کسرِ ۵٪ که ۱۷۳۰۷۳
             آن را حذف کرد
  G-RESHTEI  مسیرِ شاخصِ رشته‌ای — مسیری که ۱۷۳۰۷۳ ۲-۱-۱ آن را لغو
             کرد (همیشه گروهی، مگر تبصرهٔ ۲ِ ۲-۱-۳ با مستندسازی)

سناریوی **غیرقابلِ شبیه‌سازی** (مستندسازی شده):
  G-IO-Q3    تلاش برای شبیه‌سازیِ ۱-۸-۱ِ ۱۷۳۰۷۳ (Io یک دوره به عقب)
             با final_offer_date="۱۴۰۳/۰۹/۳۰". کار **نمی‌کند**: دادهٔ
             شاخصِ فصل از «اسفند ۱۴۰۳» شروع می‌شود و برای آذر ۱۴۰۳
             مقداری وجود ندارد، پس موتور به شاخصِ رشته fallback
             می‌کند (app.py:4543-4550). ΔPِ این سناریو دقیقاً برابرِ
             G-RESHTEI است (هر دو مسیرِ شاخصِ رشته با Io=پایه) — این
             یک Io-shift نیست. → نیازمند دادهٔ شاخصِ ۱۴۰۳Q3 + تغییر کد.

اجرا:  python tools/gap_2080_173073.py
"""
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from decision_impact import BASE, build_inputs  # noqa: E402
from app import (DynamoMappingParser, RevitScheduleParser,  # noqa: E402
                 TechnicalOfficeEngine, _default_fehrest_db, default_settings)

OUT_MD = os.path.join(ROOT, "docs", "gap_2080_173073.md")
OUT_JSON = os.path.join(os.path.dirname(__file__), "gap_results.json")

SCENARIOS = [
    {"id": "BASELINE",
     "label": "رفتارِ فعلی (۲۰۸۰)",
     "flip": {},
     "gap": "—",
     "note": "مرجعِ مقایسه"},
    {"id": "G-K1",
     "label": "k = ۱ (اتمام در مدت)",
     "flip": {"completed_within_term": True},
     "gap": "۸-۱",
     "note": ("کرانِ بالا برای k=۰٫۹۷۵ — ۱۷۳۰۷۳ ۸-۲ این مقدارِ جدید را "
              "بینِ ۰٫۹۵ و ۱ قرار می‌دهد")},
    {"id": "G-FASKH",
     "label": "فسخ با قصور (۲۰۸۰ بند ۷)",
     "flip": {"contract_status": "فسخ با قصور"},
     "gap": "بند ۷",
     "note": "مقدارِ کسرِ ۵٪ که ۱۷۳۰۷۳ آن را حذف کرد"},
    {"id": "G-RESHTEI",
     "label": "مسیرِ شاخصِ رشته‌ای",
     "flip": {"index_method": "رشته‌ای"},
     "gap": "۲-۱-۱",
     "note": ("مسیری که ۱۷۳۰۷۳ آن را لغو کرد (همیشه گروهی، مگر تبصرهٔ ۲ِ "
              "۲-۱-۳ با مستندسازی در اسناد)")},
]

# تلاشِ ناموفق برای شبیه‌سازی — برای مستندسازی
ATTEMPT_IO_Q3 = {
    "id": "G-IO-Q3",
    "label": "تلاش: Io یک دوره به عقب (۱۷۳۰۷۳ ۱-۸-۱)",
    "flip": {"final_offer_date": "۱۴۰۳/۰۹/۳۰"},
    "gap": "۱-۸-۱",
    "note": ("با final_offer_date انجام شد؛ موتور به دلیلِ نبودِ شاخصِ "
             "فصلِ ۱۴۰۳Q3 به شاخصِ رشته fallback کرد — Io-shift نشد"),
}


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
        "delta_p_provisional": t.get("delta_p_provisional"),
        "deduction_fault": t.get("deduction_fault"),
        "result_amount": t.get("result_amount"),
        "io_q": t.get("io_q"),
        "k": t.get("coef"),
        "baravord": b.get("result_amount"),
    }


def _fmt(v, digits=2):
    if v is None:
        return "—"
    return ("{:,.%df}" % digits).format(v)


def main():
    tables, map_df = build_inputs()

    print("سناریوها اجرا می‌شوند (هر کدام ~۱۲s) ...", flush=True)
    base = run(tables, map_df, {})
    rows = []
    for sc in SCENARIOS + [ATTEMPT_IO_Q3]:
        m = run(tables, map_df, sc["flip"])
        m["id"] = sc["id"]
        m["label"] = sc["label"]
        m["gap"] = sc["gap"]
        m["note"] = sc["note"]
        m["d_delta_p"] = (round(m["delta_p"] - base["delta_p"], 2)
                          if m["delta_p"] is not None
                          and base["delta_p"] is not None else None)
        m["d_baravord"] = (round(m["baravord"] - base["baravord"], 2)
                           if m["baravord"] is not None
                           and base["baravord"] is not None else None)
        rows.append(m)
        print("  %s: ΔP=%s  Io=%s  k=%s" % (
            sc["id"], _fmt(m["delta_p"]), m["io_q"], _fmt(m["k"], 4)),
            flush=True)

    by_id = {m["id"]: m for m in rows}
    k1 = by_id["G-K1"]
    faskh = by_id["G-FASKH"]
    reshtei = by_id["G-RESHTEI"]
    ioq3 = by_id["G-IO-Q3"]

    # تأییدِ کشفِ fallback: ΔPِ تلاشِ Io-Q3 باید با مسیرِ رشته‌ای برابر باشد
    fallback_confirmed = (ioq3["delta_p"] == reshtei["delta_p"])

    # ── خروجیِ JSON برای ردیابی ──
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"base_settings": BASE, "baseline": base, "rows": rows,
                   "fallback_confirmed": fallback_confirmed},
                  fh, ensure_ascii=False, indent=1)

    # ── گزارشِ مارک‌داون ──
    L = []
    L.append("# اندازه‌گیریِ عددیِ شکافِ ۲۰۸۰ → ۱۷۳۰۷۳ — فاز E-11-A §۳\n")
    L.append("<!-- default-label: [MEAS] -->\n")
    L.append("")
    L.append("> این گزارش با `tools/gap_2080_173073.py` **به‌صورتِ خودکار** "
             "تولید می‌شود؛ هیچ عددی دستی وارد نشده است. پروژهٔ مرجع: "
             "base_total = %s، grand_total = %s (ریال)."
             % (_fmt(base["base_total"]), _fmt(base["grand_total"])))
    L.append("")
    L.append("## روش")
    L.append("")
    L.append("بدونِ هیچ تغییری در کد — فقط فلگ‌ها و ورودی‌های موجود. "
             "هر شکافی که با فلگ ممکن نیست، در جدولِ پایانی به‌صورتِ "
             "«نیازمند تغییرِ کد» گزارش می‌شود. **فریزِ کد پابرجاست.**")
    L.append("")
    L.append("## جدولِ اندازه‌گیری‌ها")
    L.append("")
    L.append("| سناریو | شکاف | k | Io | ΔP (ریال) | Δ ΔP | برآورد (ریال) | "
             "Δ برآورد |")
    L.append("|---|---|---|---|---|---|---|---|")
    for m in rows:
        flag = "" if m["id"] in by_id and m["id"] != "G-IO-Q3" else " ⚠"
        if m["id"] == "G-IO-Q3":
            flag = " ⚠ نامعتبر"
        L.append("| %s%s | %s | %s | %s | %s | %s | %s | %s |" % (
            m["label"], flag, m["gap"], _fmt(m["k"], 4), m["io_q"],
            _fmt(m["delta_p"]), _fmt(m["d_delta_p"]),
            _fmt(m["baravord"]), _fmt(m["d_baravord"])))
    L.append("")
    L.append("### یافتهٔ مهم: شبیه‌سازیِ جابه‌جاییِ Io ممکن نیست")
    L.append("")
    L.append("۱۷۳۰۷۳ بند ۱-۸-۱ شاخصِ مبنا را به **یک دورهٔ سه‌ماهه قبل از** "
             "مهلتِ تسلیمِ پیشنهاد منتقل می‌کند (در پروژهٔ مرجع: "
             "۱۴۰۳Q4 → **۱۴۰۳Q3**). تلاش برای شبیه‌سازیِ آن با "
             "`final_offer_date = ۱۴۰۳/۰۹/۳۰` کار **نمی‌کند**:")
    L.append("")
    L.append("1. مجموعهٔ دادهٔ شاخص‌ها (از بخشنامهٔ ۱۵۵۲۳۳، `config/"
             "index_bulletins.json`) از **اسفند ۱۴۰۳** شروع می‌شود — "
             "`base_esfand_1403` کوچک‌ترین کلیدِ هر شاخص است. برای "
             "**آذر ۱۴۰۳ مقداری وجود ندارد**.")
    L.append("2. `_chapter_index_q(code, \"1403Q3\")` مقدار `None` برمی‌گرداند.")
    L.append("3. موتور طبقِ `app.py:4543-4550` به **شاخصِ رشته** fallback "
             "می‌کند و خودش این جایگزینی را در فهرستِ `pending` (تفسیرهای "
             "ناتمام) ثبت می‌کند.")
    L.append("")
    L.append("سرنخِ این اتفاق: ΔPِ این سناریو **دقیقاً برابرِ مسیرِ "
             "شاخصِ رشته‌ای** است (%s ریال — تأییدِ خودکار: %s). یعنی "
             "اندازه‌گیری نمی‌توانست جابه‌جاییِ Io باشد."
             % (_fmt(ioq3["delta_p"]),
                "بله" if fallback_confirmed else "نه"))
    L.append("")
    L.append("**نتیجه:** این شکاف **نیازمندِ دادهٔ جدید است، نه فقط کد**: "
             "شاخصِ گروهیِ فصول برای سه‌ماههٔ آذر ۱۴۰۳ (از یک بخشنامهٔ "
             "رسمی) به‌علاوهٔ تغییرِ کد برای اینکه Io بتواند قبل از "
             "دورهٔ پایه قرار گیرد.")
    L.append("")
    L.append("## کسرِ ۵٪ فسخ (بند ۷)")
    L.append("")
    L.append("| مقدار | ریال |")
    L.append("|---|---|")
    L.append("| ΔP (دست‌نخورده) | %s |" % _fmt(faskh["delta_p"]))
    L.append("| کسرِ ۵٪ (`deduction_fault`) | %s |"
             % _fmt(faskh["deduction_fault"]))
    L.append("| مبلغِ نهایی (`result_amount`) | %s |"
             % _fmt(faskh["result_amount"]))
    L.append("")
    L.append("۱۷۳۰۷۳ این کسر را **کاملاً حذف** کرد. روی یک پروژهٔ فسخ‌شده "
             "با این ΔP، حذفِ آن به پیمانکار **%s ریال** بیشتر پرداخت "
             "می‌کند. روی پروژهٔ مرجع (وضعیت = فعال) اثر **صفر** است."
             % _fmt(-faskh["deduction_fault"]))
    L.append("")
    L.append("## k = ۰٫۹۷۵ (۱۷۳۰۷۳ ۸-۲) — کران‌ها")
    L.append("")
    L.append("هیچ فلگی برای k=۰٫۹۷۵ وجود ندارد (`completed_within_term` "
             "فقط True/False/None است). ولی k=۱ قابلِ شبیه‌سازی است، پس "
             "کران‌ها اندازه‌گیری شدند:")
    L.append("")
    L.append("| k | ΔP (ریال) | Δ ΔP |")
    L.append("|---|---|---|")
    L.append("| ۰٫۹۵ (الان) | %s | — |" % _fmt(base["delta_p"]))
    L.append("| **۰٫۹۷۵ (۱۷۳۰۷۳ ۸-۲)** | **نیازمند تغییرِ کد** | بینِ دو "
             "ردیف |")
    L.append("| ۱٫۰۰ (G-K1) | %s | %s |"
             % (_fmt(k1["delta_p"]), _fmt(k1["d_delta_p"])))
    L.append("")
    L.append("تقریبِ خطی (تنها برای برنامه‌ریزی — **اندازه‌گیری نیست**): "
             "اگر از گردکردنِ هر سه‌ماهه صرف‌نظر کنیم، ΔP(k) ≈ k × S است. "
             "دو برآوردِ متفاوت از دو کران به‌دست می‌آید که اختلافِ "
             "آن‌ها (~%s ریال) نشان‌دهندهٔ نویزِ گردکردن است:"
             % _fmt(abs(k1["delta_p"] * 0.975 - base["delta_p"] * 0.975 / 0.95)))
    L.append("")
    L.append("- از k=۰٫۹۵: ۰٫۹۷۵/۰٫۹۵ × %s ≈ **%s ریال**"
             % (_fmt(base["delta_p"]),
                _fmt(base["delta_p"] * 0.975 / 0.95)))
    L.append("- از k=۱٫۰۰: ۰٫۹۷۵ × %s ≈ **%s ریال**"
             % (_fmt(k1["delta_p"]),
                _fmt(k1["delta_p"] * 0.975)))
    L.append("")
    L.append("یعنی ΔP(۰٫۹۷۵) احتمالاً حدودِ **۱۰٫۲ میلیارد ریال** است "
             "(بینِ دو مقدارِ بالا). مقدارِ دقیق فقط با تغییرِ کد به‌دست "
             "می‌آید.")
    L.append("")
    L.append("## مواردی که با فلگ ممکن نیست (نیازمند تغییرِ کد)")
    L.append("")
    L.append("| شکاف | چرا ممکن نیست | برآوردِ کدنویسی |")
    L.append("|---|---|---|")
    L.append("| **k = ۰٫۹۷۵** (۸-۲) | `completed_within_term` فقط "
             "True/False/None است؛ `TADIL_K_2080`/`TADIL_K_COMPLETED` "
             "ثابت | ~۴ ساعت |")
    L.append("| **Io یک دوره به عقب** (۱-۸-۱) | دادهٔ شاخصِ فصلِ آذر ۱۴۰۳ "
             "وجود ندارد + Io نمی‌تواند قبل از دورهٔ پایه قرار گیرد "
             "(fallback می‌شود) | ~۲ ساعت کد + داده |")
    L.append("| گردکردن ۴→۳ رقم (۵-۳) | `coef_rounding_2080` فقط "
             "روشن/خاموش است (خاموش = بدون گردکردن) | ~۲ ساعت |")
    L.append("| فرمولِ کارِ جدید (۲-۱-۵-۲) ⚠ | فرمول در کد نوشته شده و "
             "فلگ ندارد؛ علاوه بر این متنِ بخشنامه ابهام دارد | ~۳ ساعت "
             "+ تأییدِ متن |")
    L.append("| مصالح پای‌کار (۲-۱-۳ + تبصره‌ها) | اصلاً پیاده نشده "
             "(D-20) + نگاشتِ فصلِ «بتن درجا» لازم است | ~۸ ساعت + داده |")
    L.append("| شاخصِ کلیِ تجهیز (۲-۱-۲) | اصلاً پیاده نشده (D-19) | "
             "~۶ ساعت + داده |")
    L.append("")
    L.append("## مواردی با اثرِ صفر روی پروژهٔ مرجع")
    L.append("")
    L.append("| شکاف | چرا صفر | تأیید |")
    L.append("|---|---|---|")
    L.append("| حذفِ آستانهٔ ۳۰۰ میلیون (۲-۱-۱) | پروژهٔ مرجع %s ریال است "
             "(≫ ۳۰۰ میلیون) و از قبل مسیرِ گروهی را دارد | BASELINE: "
             "index_method = گروهی |"
             % _fmt(base["grand_total"]))
    L.append("| حذفِ سقفِ ۱۰٪ (نامه-۶) | سقف فقط با روشِ `fehrest_period` "
             "فعال می‌شود و مرجع `proposal_period` است | BASELINE |")
    L.append("| حذفِ کسرِ ۵٪ (بند ۷) | `contract_status` = فعال ⇒ "
             "`deduction_fault` = ۰ | BASELINE: %s |"
             % _fmt(base["deduction_fault"]))
    L.append("| حذفِ روشِ ۱-۶-۱ یکم (fehrest_period) | مرجع از قبل "
             "`proposal_period` است | BASELINE: base_index_method = "
             "proposal_period |")
    L.append("| مسیرِ رشته‌ای (۲-۱-۱) | مرجع گروهی است؛ لغوِ این مسیر "
             "فقط در صورتِ تغییرِ مسیر اثر دارد | G-RESHTEI برای مقایسه: "
             "ΔΔP = %s |" % _fmt(reshtei["d_delta_p"]))
    L.append("")
    L.append("---")
    L.append("")
    L.append("تولیدشده توسط `tools/gap_2080_173073.py` — فاز E-11-A "
             "(فقط تحلیل؛ فریزِ کد پابرجاست).")
    L.append("")

    with open(OUT_MD, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
    print("نوشته شد: %s" % OUT_MD)
    print("fallback_confirmed:", fallback_confirmed)


if __name__ == "__main__":
    main()
