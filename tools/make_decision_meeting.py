# -*- coding: utf-8 -*-
"""tools/make_decision_meeting.py — فاز E-10 §۵ (بازبانیِ فاز E-10.1 §۱).

بستهٔ جلسهٔ تصمیم را می‌سازد:
  - docs/DECISION_MEETING.md
  - docs/DECISION_MEETING.docx  (با نمودارِ tornado — بدون کتابخانهٔ
    نمودار؛ از جدولِ سایه‌زده استفاده می‌شود)

ورودی‌ها (هیچ عددی حدس زده نمی‌شود):
  - tools/decision_impact_scenarios.json — اندازه‌گیریِ هر تصمیم روی
    پروژهٔ مرجع (فاز E-9 §۱، بازتولیدشده در E-10 §۳)
  - اجرای سه سناریوی ترکیبی روی پروژهٔ مرجع با همان موتور

ساختارِ سند:
   ۱) مقدمه + اعدادِ پایه
   ۲) ۵ تصمیمِ اول (بیشترین |اثر|) در یک صفحهٔ جدا
   ۳) همهٔ تصمیم‌ها — مرتب بر اساس max |اثر| + منبعِ هر توصیه
   ۴) تحلیل حساسیت — سه سناریو + یادداشتِ هم‌کنش
   ۵) بازهٔ حساسیتِ واقعی (envelope) — چهار سناریوی اجرای همزمان (فاز E-10.1 §۱)
   ۶) نمودار tornado
اجرا:  python tools/make_decision_meeting.py
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from decision_impact import build_inputs, fa_num, run  # noqa: E402

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
SCEN_PATH = os.path.join(os.path.dirname(__file__),
                         "decision_impact_scenarios.json")

# ── سناریوهای ترکیبیِ جلسه ──
#
# S1 = همهٔ الف (وضعیتِ فعلی). S2 = گزینهٔ بِ همهٔ تصمیم‌های قابلِ
# پیاده‌شدهٔ مستقل. S3 = توصیهٔ ما: از آنجا که متنِ بخشنامه همهٔ گزینه‌های
# بِ قابلِ اجرا را رد می‌کند (فاز E-10 §۳)، توصیهٔ ما همان S1 است؛ این
# تشریح می‌شود تا دو عددِ یکسان معترک نشود.
CONTRACT_EXT = [{"date": "۱۴۰۵/۰۲/۱۵", "months": 3, "kind": "مجاز",
                 "doc_no": "سناریوی ابزار"}]

SCENARIOS = [
    {"id": "S1", "name": "همهٔ الف (وضعیتِ فعلی)",
     "flips": {},
     "desc": "همهٔ تصمیم‌ها با گزینهٔ الف (پیش‌فرضِ فعلی) حل می‌شوند."},
    {"id": "S2", "name": "همهٔ بِ قابلِ پیاده‌شده",
     "flips": {"completed_within_term": True,
               "coef_rounding_2080": False,
               "negative_coef_rounding": "toward_zero",
               "fault_deduction_on_negative": True,
               "provisional_diff_method": "own_period",
               "contract_extensions": CONTRACT_EXT,
               "index_method": "رشته‌ای"},
     "desc": ("گزینهٔ بِ هفت تصمیمِ مستقلِ قابلِ پیاده‌شده با هم اعمال "
              "می‌شود (D-01، D-03، D-04، D-08، D-09، D-10، D-13). "
              "D-14/D-15/D-16 سناریوی فرضیِ کارِ جدیدِ ۱ میلیارد ریالی‌اند "
              "و روی پروژهٔ مرجع کارِ جدیدی وجود ندارد، اینجا اعمال "
              "نمی‌شوند.")},
    {"id": "S3", "name": "توصیهٔ ما",
     "flips": {},
     "same_as": "S1",
     "desc": ("توصیهٔ ما **همان S1 است**: متنِ بخشنامه (فاز E-10 §۳) "
              "گزینه‌های ب را رد می‌کند و برای بقیه، اثرِ اندازه‌گیری‌شده "
              "صفر است. تنها استثنا D-01 است که یک **واقعیتِ پروژه** است، "
              "نه یک انتخابِ طراحی — ردیفِ شرطیِ پایین را ببینید.")},
]

# شرطِ D-01: اگر کارفرما تأیید کند که کار در مدتِ پیمان تمام شده،
# k = ۱ می‌شود (تبصرهٔ ۲). این یک حدس نیست — یک شرطِ صریح است.
D01_CONDITIONAL = {"id": "S3+D01", "flips": {"completed_within_term": True}}

# ── کانال‌های پولی برای رتبه‌بندیِ max |اثر| ──
CHANNELS = [("d_delta_p", "ΔP"), ("d_baravord", "برآورد به‌هنگام")]


def load_measured():
    with open(SCEN_PATH, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload


def max_effect(res):
    """بیشترین |اثر| روی هر کانالِ پولی (ΔP / برآورد / سقف)."""
    vals = []
    for key, _label in CHANNELS:
        v = res.get(key)
        if v is not None:
            vals.append(abs(v))
    v = res.get("d_ceiling")
    if v is not None:
        vals.append(abs(v))
    return max(vals) if vals else None


def effect_channels(res):
    """متنِ کانال‌هایی که عددِ غیرصفر دارند."""
    out = []
    for key, label in CHANNELS:
        v = res.get(key)
        if v is not None and abs(v) >= 0.005:
            out.append("%s: %s" % (label, fa_num(v)))
    v = res.get("d_ceiling")
    if v is not None and abs(v) >= 0.005:
        out.append("سقفِ ۱۰٪: %s" % fa_num(v))
    return out


# ── سناریوهای فرضیِ کارِ جدید (تزریقِ ۱ میلیارد ریال) — [FIX] ──
FIX_IDS = ("D-14", "D-15", "D-16")

DATE = "۱۴۰۵/۰۷/۱۴"          # فاز E-10 §۵
REV_DATE = "۱۴۰۵/۰۷/۱۵"      # فاز E-10.1 §۱ (بازهٔ حساسیت)


def pct(part, whole):
    if not whole:
        return "—"
    return fa_num(100.0 * part / whole, 2)


def build_markdown(base_m, scen_results, rows, results, envelope):
    L = []
    a = L.append
    a("# بستهٔ جلسهٔ تصمیم — پروژهٔ MetreYar2")
    a("")
    a("<!-- default-label: [REF] -->")
    a("")
    a("**تاریخِ اولیه:** %s (فاز E-10 §۵)؛ **بازبینی:** %s (فاز E-10.1 §۱ — بازهٔ حساسیت و منبعِ توصیه‌ها). این سند با `tools/make_decision_meeting.py` "
      "از یک منبعِ واحد ساخته شده و با `docs/PENDING_DECISIONS.md` و "
      "`docs/DECISION_IMPACT.md` هم‌خوان است." % (DATE, REV_DATE))
    a("")
    a("> **قاعدهٔ طلایی:** هیچ عددی در این سند حدس زده نشده است. هر عدد "
      "یا با اجرای واقعیِ موتور روی پروژهٔ مرجع به‌دست آمده، یا مستقیم از "
      "متنِ بخشنامه نقل شده [SRC].")
    a("")
    a("**اعدادِ پایهٔ پروژهٔ مرجع:** base_total = %s، grand_total = %s، "
      "ΔP = %s، برآورد به‌هنگام = %s ریال."
      % (fa_num(base_m["base_total"]), fa_num(base_m["grand_total"]),
         fa_num(base_m["delta_p"]), fa_num(base_m["baravord"])))
    a("")
    a("---")
    a("")
    # ── ۱) ۵ تصمیمِ اول ──
    a("## ۵ تصمیمِ اول — بیشترین |اثر|")
    a("")
    top = [r for r in rows if r["rank"] <= 5]
    for r in top:
        a("### %s — %s" % (r["id"], r["subject"]))
        a("")
        a("- **گزینهٔ الف (الان):** %s" % r["option_a"])
        a("- **گزینهٔ ب:** %s" % r["option_b"])
        a("- **بیشترین اثر:** %s ریال%s"
          % (fa_num(r["max_effect"]),
             " — سناریوی فرضیِ کارِ جدید [FIX]" if r["id"] in FIX_IDS else ""))
        if r["channels"]:
            a("- **کانال‌ها:** %s" % "؛ ".join(r["channels"]))
        a("- **توصیهٔ ما:** %s" % r["recommendation"])
        _lbl, _det = r["rec_source"]
        a("- **منبع توصیه:** [%s] %s" % (_lbl, _det))
        a("")
    a("---")
    a("")
    # ── ۲) همهٔ تصمیم‌ها ──
    a("## همهٔ تصمیم‌ها — مرتب بر اساس max |اثر|")
    a("")
    a("ردیف‌های با علامتِ * سناریوی فرضیِ تزریقِ کارِ جدیدِ ۱ میلیارد "
      "ریالی‌اند [FIX] — روی پروژهٔ مرجع کارِ جدیدی وجود ندارد و این "
      "اعداد فقط برای مقیاس‌دادن به اثرِ تصمیم نشان داده می‌شوند.")
    a("")
    a("| رتبه | شناسه | موضوع | گزینهٔ ب | max \|اثر\| (ریال) | کانال | توصیه | منبع |")
    a("|---|---|---|---|---|---|---|---|")
    for r in rows:
        star = " *" if r["id"] in FIX_IDS else ""
        a("| %d | %s%s | %s | %s | %s | %s | %s | [%s] |"
          % (r["rank"], r["id"], star, r["subject"], r["option_b"],
             fa_num(r["max_effect"]) if r["max_effect"] is not None else "—",
             "، ".join(r["channels"]) if r["channels"] else "—",
             r["recommendation"], r["rec_source"][0]))
    a("")
    a("---")
    a("")
    # ── ۳) تحلیل حساسیت ──
    a("## تحلیل حساسیت — سه سناریو")
    a("")
    a("| سناریو | شرح | ΔP (ریال) | برآورد (ریال) |")
    a("|---|---|---|---|")
    for s in SCENARIOS:
        m = scen_results[s["id"]]
        a("| **%s** — %s | %s | %s | %s |"
          % (s["id"], s["name"], s["desc"], fa_num(m["delta_p"]),
             fa_num(m["baravord"])))
    d01 = scen_results["S3+D01"]
    a("| **شرطی** — توصیه + تأییدِ D-01 (اتمامِ کار در مدتِ پیمان ⇒ k=۱) | "
      "اگر کارفرما این واقعیت را تأیید کند | %s | %s |"
      % (fa_num(d01["delta_p"]), fa_num(d01["baravord"])))
    a("")
    dps = [scen_results[s["id"]]["delta_p"] for s in SCENARIOS]
    lo, hi = min(dps), max(dps)
    spread = hi - lo
    a("**بازهٔ کمینه تا بیشینهٔ ΔP:** از %s تا %s ریال یعنی بازه‌ای به "
      "پهنای %s ریال (= %s٪ از ΔPِ فعلی، %s٪ از base_total)."
      % (fa_num(lo), fa_num(hi), fa_num(spread), pct(spread, dps[0]),
         pct(spread, base_m["base_total"])))
    a("")
    # مجموعِ اثرهای فردی در برابرِ ترکیب (هم‌کنش)
    flip_ids = ("D-01", "D-03", "D-04", "D-08", "D-09", "D-10", "D-13")
    naive = sum((results[i].get("d_delta_p") or 0.0) for i in flip_ids)
    inter = spread - naive
    a("> **هم‌کنش:** مجموعِ اثرهای فردیِ هفت تصمیم = %s ریال است، ولی "
      "اعمالِ همزمانِ آن‌ها %s ریال تغییر می‌دهد. اختلافِ %s ریال "
      "اثرِ تقاطعِ تصمیم‌هاست (مثلاً اثرِ k روی مسیرِ رشته‌ای متفاوت "
      "از مسیرِ گروهی است) — به همین دلیل سناریوها به‌جای جمع‌زدن، "
      "اجرای همزمان می‌شوند."
      % (fa_num(naive), fa_num(spread), fa_num(inter)))
    a("")
    a("> **قرائت:** چون S1 و S3 یکی هستند، کل بازهٔ حساسیتِ تصمیم‌های "
      "قابلِ پیاده‌شده برابرِ |S2 − S1| است. بزرگ‌ترین تک‌اثر اما "
      "خارج از این بازه است: D-18 (سقفِ ۱۰٪) با %s ریال اختلافِ سقف، و "
      "D-01 با %s ریال که شرطی است، نه انتخاب."
      % (fa_num(results["D-18"]["d_ceiling"]),
         fa_num(results["D-01"]["d_delta_p"])))
    a("")
    a("---")
    a("")
    # ── ۴) tornado ──
    # ── ۴-ب) بازهٔ حساسیتِ واقعی (فاز E-10.1 §۱) ──
    a("## بازهٔ حساسیتِ واقعی (envelope)")
    a("")
    a("برای هر سنجه، سناریوی کمینه و بیشینه با **اجرای همزمان** "
      "گزینه‌هایی که سنجه را در جهتِ دلخواه حرکت می‌دهند ساخته شده‌اند "
      "(جمع‌زدنِ اثرهای فردی ممنوع است — بالا ببینید). تصمیم‌های با اثرِ "
      "صفر روی پروژهٔ مرجع (D-04، D-08، D-09، D-10) در هیچ سناریویی چیزی "
      "را تغییر نمی‌دهند.")
    a("")
    a("| سناریو | ΔP (ریال) | برآورد (ریال) | تصمیم‌های اعمال‌شده |")
    a("|---|---|---|---|")
    for e in ENVELOPE:
        m = envelope[e["id"]]
        a("| **%s** | %s | %s | %s |"
          % (e["name"], fa_num(m["delta_p"]), fa_num(m["baravord"]),
             "، ".join(m["flips"]) if m["flips"] else "هیچ (همهٔ الف)"))
    a("")
    _lo = min(envelope["E-min-dp"]["delta_p"], envelope["E-max-dp"]["delta_p"])
    _hi = max(envelope["E-min-dp"]["delta_p"], envelope["E-max-dp"]["delta_p"])
    _w = _hi - _lo
    a("**پهنای بازهٔ ΔP:** از %s تا %s ریال یعنی %s ریال (= %s٪ از ΔPِ "
      "فعلی)." % (fa_num(_lo), fa_num(_hi), fa_num(_w),
                  pct(_w, base_m["delta_p"])))
    _lo2 = min(envelope["E-min-bar"]["baravord"],
               envelope["E-max-bar"]["baravord"])
    _hi2 = max(envelope["E-min-bar"]["baravord"],
               envelope["E-max-bar"]["baravord"])
    _w2 = _hi2 - _lo2
    a("**پهنای بازهٔ برآورد:** از %s تا %s ریال یعنی %s ریال (= %s٪ از "
      "برآوردِ فعلی)." % (fa_num(_lo2), fa_num(_hi2), fa_num(_w2),
                          pct(_w2, base_m["baravord"])))
    a("")
    _fixd = [f for f in envelope["E-max-dp"]["flips"] if "[FIX]" in f]
    _fix_name = _fixd[0].split(" ")[0] if _fixd else "هیچ"
    a("> **تفاوت با بازهٔ S1–S2:** این بازه شاملِ سناریوهای فرضیِ کارِ جدید "
      "[FIX] هم می‌شود (فقط در سناریوهای بیشینه). اگر فقط گزینه‌های واقعیِ "
      "پروژهٔ مرجع مدّ نظر باشد، بازه همان S1 تا S2 در جدولِ بالاست.")
    a("")
    a("### چرا D-14/D-15 در بازهٔ برآوردِ E-10 نبودند — و حالا هستند")
    a("")
    a("در فاز E-10 §۵ بازهٔ برآورد فقط سناریوهای S1/S2/S3 را در بر "
      "می‌گرفت و آن‌ها عمداً سناریوی **فرضیِ کارِ جدید** (D-14/D-15/D-16 با "
      "تزریقِ ۱ میلیارد ریال) را شامل نمی‌شدند، چون روی پروژهٔ مرجع کارِ "
      "جدیدی وجود ندارد [FIX].")
    a("")
    a("> **اصلاحِ یک ادعای E-9:** گزارشِ E-9 اثرِ D-14 روی برآورد را "
      "«+۲٬۴۷۰٬۸۶۱٬۰۸۳٫۱۳ ریال» و D-15 را «+۲٬۳۳۳٬۴۶۳٬۵۸۰٫۸۴ ریال» نوشته "
      "است. این دو عدد در **هیچ فایل و هیچ کامیتی** از مخزن وجود ندارند "
      "(جستجوی دقیق در تمامِ تاریخچهٔ git). همهٔ کامیت‌های E-9 (8f48a01، "
      "2204d64، ed6d133، 8ca9e21) و اجرایِ مجددِ موتور مقدارهای "
      "**+۱٬۴۷۰٬۸۶۱٬۰۸۳٫۴۶** (D-14) و **+۱٬۳۳۳٬۴۶۳٬۵۸۰٫۷۳** (D-15) را "
      "می‌دهند. اختلافِ دقیقاً ۱ میلیارد ریال (= مبلغِ خامِ کارِ جدیدِ "
      "تزریق‌شده) نشان می‌دهد که اعدادِ ادعا‌شده اصلِ مبلغ را **دو بار** "
      "حساب کرده‌اند. مقدارِ درست همان ۱٫۴۷ و ۱٫۳۳ میلیارد ریال است.")
    a("")
    a("در بازهٔ بالا، سناریوهای «بیشینه» شاملِ بهترین variantِ کارِ جدید "
      "[FIX] هستند (%s) و سناریوهای «کمینه» شاملِ هیچ کارِ جدیدی نیستند. "
      "بنابراین D-14 و D-15 حالا در بازه هستند — با برچسبِ صریحِ [FIX] و "
      "با اعدادِ قابلِ بازتولید." % _fix_name)
    a("")
    a("---")
    a("")

    a("## نمودار tornado")
    a("")
    a("هر نوار طولش متناسب با max |اثر| روی ΔP یا برآورد است (D-18 "
      "مستثنی است: اختلافِ %s ریال‌اش مربوط به **سقفِ پذیرشِ ۱۰٪** است، "
      "نه ΔP — مقیاسِ متفاوتی دارد و در نمودار جا نمی‌گیرد). یکای نوار "
      "به نسبتِ بزرگ‌ترین اثرِ غیرِ سقف تقسیم شده است."
      % fa_num(results["D-18"]["d_ceiling"]))
    a("")
    a("| شناسه | موضوع | اثر | نوار |")
    a("|---|---|---|---|")
    tor_rows = [r for r in rows if r["tornado_units"] is not None]
    md_max = max((r["tornado_units"] for r in tor_rows), default=1.0) or 1.0
    for r in tor_rows:
        u = int(round(r["tornado_units"] / md_max * 24))
        neg = r["tornado_neg"]
        bar = ("◄" if neg else "") + "█" * u + ("►" if not neg else "")
        if u == 0:
            bar = "│"
        a("| %s | %s | %s | %s |"
          % (r["id"], r["subject"],
             ("−" if neg else "+") + fa_num(r["tornado_val"]),
             bar))
    a("")
    a("نوارهای قرمز (◄) = کاهش، نوارهای سبز (►) = افزایش. طول بر اساسِ "
      "بزرگ‌ترین اثر روی هر کانال است.")
    a("")
    a("---")
    a("")
    # ── ۵) گروه‌های دیگر ──
    a("## تصمیم‌های ردشده، ادغام‌شده و منتظر داده")
    a("")
    a("- **ردشده در طراحی (۶ مورد)** با استدلال از متنِ بخشنامه — فاز "
      "E-10 §۳: D-02، D-05، D-06، D-07، D-12، D-17. هیچ گزینه‌ای در "
      "`DECISION_SHEET.md` نماند که در کد قابلِ اجرا نباشد.")
    a("- **ادغام‌شده (۱ مورد):** D-11 در D-13 (مسیرِ شاخصِ رشته‌ای).")
    a("- **منتظر دادهٔ خارجی (۲ مورد):** D-19 (شاخصِ کلیِ مستقل) و D-20 "
      "(مصالحِ پای‌کار) — تا رسیدنِ داده قابلِ تصمیم‌گیری نیستند.")
    a("- **اثر صفرِ اندازه‌گیری‌شده (۴ مورد):** D-04، D-08، D-09، D-10 — "
      "در پروژهٔ مرجع عدد را تغییر نمی‌دهند ولی پشتِ فلگ پیاده شده‌اند.")
    a("")
    a("تولیدشده با `tools/make_decision_meeting.py` (فاز E-10 §۵).")
    return "\n".join(L)


def build_docx(path, base_m, scen_results, rows, results, envelope):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Tahoma"
    style.font.size = Pt(10)
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), "Tahoma")

    def rtl(par):
        pPr = par._p.get_or_add_pPr()
        pPr.append(OxmlElement("w:bidi"))
        par.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    def para(text="", bold=False, size=None, space_after=4):
        p = doc.add_paragraph()
        rtl(p)
        r = p.add_run(text)
        r.bold = bold
        if size:
            r.font.size = Pt(size)
        p.paragraph_format.space_after = Pt(space_after)
        return p

    def shade(cell, fill):
        tcPr = cell._tc.get_or_add_tcPr()
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:fill"), fill)
        tcPr.append(shd)

    # ── ۱) جلد/مقدمه ──
    para("بستهٔ جلسهٔ تصمیم — پروژهٔ MetreYar2", bold=True, size=18)
    para("فاز E-10 §۵ — تاریخ %s" % DATE, size=10)
    doc.add_paragraph()
    para("اعدادِ پایهٔ پروژهٔ مرجع:", bold=True)
    para("base_total = %s ریال" % fa_num(base_m["base_total"]))
    para("grand_total = %s ریال" % fa_num(base_m["grand_total"]))
    para("ΔP (تعدیلِ صورت‌وضعیت) = %s ریال" % fa_num(base_m["delta_p"]))
    para("برآورد به‌هنگام = %s ریال" % fa_num(base_m["baravord"]))
    doc.add_paragraph()
    para("هر عدد با اجرای واقعیِ موتور روی پروژهٔ مرجع به‌دست آمده است. "
          "هیچ عددی حدس زده نشده است.", size=9)
    doc.add_page_break()

    # ── ۲) ۵ تصمیمِ اول ──
    para("۵ تصمیمِ اول — بیشترین |اثر|", bold=True, size=15)
    doc.add_paragraph()
    for r in [x for x in rows if x["rank"] <= 5]:
        para("%s — %s" % (r["id"], r["subject"]), bold=True, size=12)
        para("گزینهٔ الف (الان): %s" % r["option_a"], size=9)
        para("گزینهٔ ب: %s" % r["option_b"], size=9)
        fix = " — سناریوی فرضیِ کارِ جدید [FIX]" if r["id"] in FIX_IDS else ""
        para("بیشترین اثر: %s ریال%s"
             % (fa_num(r["max_effect"]), fix), size=9)
        if r["channels"]:
            para("کانال‌ها: %s" % "؛ ".join(r["channels"]), size=9)
        para("توصیهٔ ما: %s" % r["recommendation"], size=9)
        doc.add_paragraph()
    doc.add_page_break()

    # ── ۳) همهٔ تصمیم‌ها ──
    para("همهٔ تصمیم‌ها — مرتب بر اساس max |اثر|", bold=True, size=15)
    para("ردیف‌های * سناریوی فرضیِ کارِ جدیدِ ۱ میلیارد ریالی‌اند [FIX].",
         size=8)
    doc.add_paragraph()
    t = doc.add_table(rows=1, cols=8)
    t.style = "Table Grid"
    hdr = ["رتبه", "شناسه", "موضوع", "گزینهٔ ب", "max |اثر| (ریال)",
           "کانال", "توصیه", "منبع"]
    for i, h in enumerate(hdr):
        p = t.rows[0].cells[i].paragraphs[0]
        rtl(p)
        r_ = p.add_run(h)
        r_.bold = True
        r_.font.size = Pt(8)
    for r in rows:
        c = t.add_row().cells
        star = " *" if r["id"] in FIX_IDS else ""
        vals = [str(r["rank"]), r["id"] + star, r["subject"], r["option_b"],
                fa_num(r["max_effect"]) if r["max_effect"] is not None else "—",
                "، ".join(r["channels"]) if r["channels"] else "—",
                r["recommendation"], r["rec_source"][0]]
        for i, v in enumerate(vals):
            p = c[i].paragraphs[0]
            rtl(p)
            run = p.add_run(v)
            run.font.size = Pt(8)
    doc.add_page_break()

    # ── ۴) تحلیل حساسیت ──
    para("تحلیل حساسیت — سه سناریو", bold=True, size=15)
    doc.add_paragraph()
    t = doc.add_table(rows=1, cols=4)
    t.style = "Table Grid"
    for i, h in enumerate(["سناریو", "ΔP (ریال)", "برآورد (ریال)", "شرح"]):
        p = t.rows[0].cells[i].paragraphs[0]
        rtl(p)
        r_ = p.add_run(h)
        r_.bold = True
    for s in SCENARIOS:
        m = scen_results[s["id"]]
        c = t.add_row().cells
        for i, v in enumerate(["%s — %s" % (s["id"], s["name"]),
                               fa_num(m["delta_p"]),
                               fa_num(m["baravord"]), s["desc"]]):
            p = c[i].paragraphs[0]
            rtl(p)
            p.add_run(v).font.size = Pt(9)
    d01 = scen_results["S3+D01"]
    c = t.add_row().cells
    for i, v in enumerate(["شرطی — توصیه + تأیید D-01 (k=۱)",
                           fa_num(d01["delta_p"]),
                           fa_num(d01["baravord"]),
                           "اگر کارفرما تأیید کند که کار در مدتِ پیمان "
                           "تمام شده است"]):
        p = c[i].paragraphs[0]
        rtl(p)
        p.add_run(v).font.size = Pt(9)
    doc.add_paragraph()
    dps = [scen_results[s["id"]]["delta_p"] for s in SCENARIOS]
    lo, hi = min(dps), max(dps)
    spread = hi - lo
    para("بازهٔ کمینه تا بیشینهٔ ΔP: از %s تا %s ریال" % (fa_num(lo), fa_num(hi)),
         bold=True)
    para("پهنای بازه = %s ریال = %s٪ از ΔPِ فعلی، %s٪ از base_total"
         % (fa_num(spread), pct(spread, dps[0]),
            pct(spread, base_m["base_total"])))
    para("نکته: S1 و S3 یکی هستند (توضیح در جدول). بزرگ‌ترین اثرها خارج "
          "از این بازه‌اند: D-18 با %s ریال اختلافِ سقفِ پذیرش و D-01 با "
          "%s ریال که شرطی است."
         % (fa_num(results["D-18"]["d_ceiling"]),
            fa_num(results["D-01"]["d_delta_p"])), size=9)
    doc.add_page_break()

    # ── ۵) نمودار tornado ──
    # ── ۴-ب) بازهٔ حساسیت (فاز E-10.1 §۱) ──
    para("بازهٔ حساسیتِ واقعی (envelope)", bold=True, size=15)
    doc.add_paragraph()
    t = doc.add_table(rows=1, cols=4)
    t.style = "Table Grid"
    for i2, h in enumerate(["سناریو", "ΔP (ریال)", "برآورد (ریال)",
                            "تصمیم‌های اعمال‌شده"]):
        p2 = t.rows[0].cells[i2].paragraphs[0]
        rtl(p2)
        r_ = p2.add_run(h)
        r_.bold = True
    for e in ENVELOPE:
        m = envelope[e["id"]]
        c = t.add_row().cells
        _fl = "، ".join(m["flips"]) if m["flips"] else "هیچ (همهٔ الف)"
        for i2, v in enumerate([e["name"], fa_num(m["delta_p"]),
                                fa_num(m["baravord"]), _fl]):
            p2 = c[i2].paragraphs[0]
            rtl(p2)
            p2.add_run(v).font.size = Pt(9)
    doc.add_paragraph()
    _lo_dp = min(envelope["E-min-dp"]["delta_p"],
                 envelope["E-max-dp"]["delta_p"])
    _hi_dp = max(envelope["E-min-dp"]["delta_p"],
                 envelope["E-max-dp"]["delta_p"])
    _w_dp = _hi_dp - _lo_dp
    para("پهنای بازهٔ ΔP: از %s تا %s ریال یعنی %s ریال (= %s٪ از ΔPِ فعلی)"
         % (fa_num(_lo_dp), fa_num(_hi_dp), fa_num(_w_dp),
            pct(_w_dp, base_m["delta_p"])), bold=True)
    _lo_br = min(envelope["E-min-bar"]["baravord"],
                 envelope["E-max-bar"]["baravord"])
    _hi_br = max(envelope["E-min-bar"]["baravord"],
                 envelope["E-max-bar"]["baravord"])
    _w_br = _hi_br - _lo_br
    para("پهنای بازهٔ برآورد: از %s تا %s ریال یعنی %s ریال (= %s٪ از "
          "برآوردِ فعلی)" % (fa_num(_lo_br), fa_num(_hi_br), fa_num(_w_br),
                             pct(_w_br, base_m["baravord"])), bold=True)
    para("نکته: سناریوهای بیشینه شاملِ بهترین variantِ کارِ جدیدِ فرضی "
          "[FIX] هستند (تزریقِ ۱ میلیارد ریال) و سناریوهای کمینه شاملِ هیچ "
          "کارِ جدیدی نیستند. D-14/D-15 در بازهٔ فاز E-10 §۵ نبودند چون "
          "فرضی‌اند — توضیحِ کامل در نسخهٔ .md.", size=8)
    doc.add_page_break()


    para("نمودار tornado", bold=True, size=15)
    para("طولِ نوار ∝ max |اثر| روی ΔP یا برآورد. D-18 مستثنی است "
          "(اختلافِ سقفِ پذیرش = %s ریال — مقیاسِ متفاوت)."
         % fa_num(results["D-18"]["d_ceiling"]), size=8)
    doc.add_paragraph()
    tor_rows = [r for r in rows if r["tornado_units"] is not None]
    UNITS = 20
    mid = UNITS + 1
    n_cols = 1 + UNITS + 1 + UNITS + 1  # برچسب | چپ | محور | راست | عدد
    t = doc.add_table(rows=1, cols=n_cols)
    t.style = "Table Grid"
    t.autofit = False
    # هدر: دو برچسبِ جهت
    hdr_cells = t.rows[0].cells
    for i in range(n_cols):
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    hdr_cells[0].paragraphs[0].add_run("کاهش ◄").bold = True
    hdr_cells[n_cols - 1].paragraphs[0].add_run("► افزایش").bold = True
    # سطرهای داده
    max_u = max(r["tornado_units"] for r in tor_rows) or 1
    for r in tor_rows:
        c = t.add_row().cells
        u = round(r["tornado_units"] * UNITS / max_u) if r["tornado_units"] else 0
        u = min(u, UNITS)
        # برچسب
        p = c[0].paragraphs[0]
        rtl(p)
        run = p.add_run("%s" % r["id"])
        run.font.size = Pt(7)
        neg = r["tornado_neg"]
        if neg:
            for i in range(UNITS - u, UNITS):
                shade(c[i + 1], "EF9A9A")
        else:
            for i in range(0, u):
                shade(c[i + mid + 1], "A5D6A7")
        shade(c[mid], "9E9E9E")
        # عدد
        p = c[n_cols - 1].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = p.add_run(("−" if neg else "+") + fa_num(r["tornado_val"]))
        run.font.size = Pt(7)
    # عرض ستون‌ها
    for row in t.rows:
        for i, cell in enumerate(row.cells):
            if i == 0:
                w = Cm(1.6)
            elif i == n_cols - 1:
                w = Cm(2.6)
            else:
                w = Cm(0.22)
            cell.width = w
    doc.add_paragraph()
    para("قرمز = کاهش، سبز = افزایش، طوسی = محورِ صفر. طول بر اساسِ "
          "بزرگ‌ترین اثر روی هر کانال است.", size=8)
    doc.add_page_break()

    # ── ۶) گروه‌های دیگر ──
    para("تصمیم‌های ردشده، ادغام‌شده و منتظر داده", bold=True, size=15)
    doc.add_paragraph()
    para("ردشده در طراحی (۶ مورد) — فاز E-10 §۳: D-02، D-05، D-06، "
          "D-07، D-12، D-17.")
    para("ادغام‌شده (۱ مورد): D-11 در D-13 (مسیرِ شاخصِ رشته‌ای).")
    para("منتظر دادهٔ خارجی (۲ مورد): D-19 (شاخصِ کلی) و D-20 (مصالحِ "
          "پای‌کار).")
    para("اثر صفرِ اندازه‌گیری‌شده (۴ مورد): D-04، D-08، D-09، D-10.")
    doc.add_paragraph()
    para("تولیدشده با tools/make_decision_meeting.py (فاز E-10 §۵)", size=8)
    doc.save(path)


# ── توصیه‌ها (از DECISION_SHEET / PENDING_DECISIONS) ──
RECOMMENDATIONS = {
    "D-01": "وارد کردنِ واقعیتِ پروژه (دادهٔ الزامی، نه انتخاب) — تا "
            "آنگاه علی‌الحساب با k=۰٫۹۵.",
    "D-03": "الف — نصِّ بند ۸-۲ گردکردن را مقرر کرده است.",
    "D-04": "الف — بخشنامه ساکت است؛ گردکردنِ روی قدر مطلق بی‌طرف است.",
    "D-08": "الف — کسر از عددِ منفی منطقی نیست.",
    "D-09": "الف — ساده‌تر و قابلِ بازبینی.",
    "D-10": "الف — تمدیدِ مجازی ثبت نشده است.",
    "D-13": "الف — بند ۲-۲ برایِ «۳۰۰ میلیون و بیشتر» مسیرِ گروهی را "
            "مقرر کرده است.",
    "D-14": "الف — بند ۳-۵: «مثلِ سایر ردیف‌ها تعدیل می‌شود».",
    "D-15": "الف — حدس زدنِ دوره خلافِ قاعدهٔ طلایی است.",
    "D-16": "الف — ادامه با پیش‌فرضِ مکتوب بهتر از توقف است.",
    "D-18": "الف — نامه-۶ صریحاً «بر اساس قیمت‌های پایه» می‌گوید.",
    "D-19": "تا رسیدنِ داده تعیین نمی‌شود (الف موقت است).",
    "D-20": "تا رسیدنِ داده تعیین نمی‌شود (الف موقت است).",
}


# ── فاز E-10.1 §۱ — منبعِ هر توصیه ──
# هر توصیه یا از نصِّ بخشنامه می‌آید [متن بخشنامه]، یا یک رویهٔ رایج است که
# نیازمند تأییدِ مشاور است [رویهٔ رایج، نیازمند تأیید مشاور]، یا یک انتخابِ
# مهندسی در جایی است که بخشنامه ساکت است [انتخاب مهندسی]. توصیه‌هایی که
# فقط «وضعیتِ فعلی» را تکرار می‌کنند با همان برچسب علامت می‌خورند. D-01 یک
# توصیه نیست — یک دادهٔ ورودیِ الزامی است.
REC_SOURCE = {
    "D-01": ("دادهٔ ورودی — واقعیتِ پروژه",
             "بند ۱-۸ + تبصرهٔ ۲: ضریب k از یک واقعیتِ پروژه (اتمام کار در "
             "مدتِ پیمان) مشتق می‌شود، نه از یک انتخابِ طراحی."),
    "D-03": ("متن بخشنامه",
             "بند ۸-۲: ضریبِ هر سه‌ماهه با ۳ رقم اعشار حساب و سپس به ۲ رقم "
             "اعشار گرد می‌شود."),
    "D-04": ("انتخاب مهندسی",
             "بخشنامه دربارهٔ جهتِ گردکردنِ ضرایبِ منفی ساکت است؛ گردکردنِ "
             "روی قدر مطلق بی‌طرفانه است."),
    "D-08": ("انتخاب مهندسی",
             "بند ۷ کسر را مقرر کرده ولی دربارهٔ ΔPِ منفی ساکت است؛ کسر از "
             "عددِ منفی منطقی نیست."),
    "D-09": ("رویهٔ رایج، نیازمند تأیید مشاور",
             "تفسیرِ بند ۲-۶: رفتارِ اتمیک ساده‌تر و قابلِ بازبینی است."),
    "D-10": ("وضعیت فعلی",
             "تمدیدِ مجازی در پروژهٔ مرجع ثبت نشده؛ توصیه‌ای جز گزینهٔ الف "
             "معنا ندارد."),
    "D-13": ("متن بخشنامه",
             "بند ۲-۲: پیمان‌های «۳۰۰ میلیون ریال و بیشتر» از مسیرِ گروهی "
             "استفاده می‌کنند."),
    "D-14": ("متن بخشنامه",
             "بند ۳-۵: کارِ جدید «مثلِ سایر ردیف‌ها تعدیل می‌شود»."),
    "D-15": ("متن بخشنامه",
             "بندهای ۳-۲/۳-۳: دورهٔ شاخصِ مبنا باید وارد شود؛ حدس زدنش "
             "مجاز نیست."),
    "D-16": ("رویهٔ رایج، نیازمند تأیید مشاور",
             "ادامه با یک پیش‌فرضِ مکتوب بهتر از توقفِ موتور است."),
    "D-18": ("متن بخشنامه",
             "نامه-۶ صریحاً «بر اساس قیمت‌های پایه» می‌گوید."),
    "D-19": ("وضعیت فعلی",
             "تا رسیدنِ دادهٔ شاخصِ کلیِ مستقل تعیین نمی‌شود؛ گزینهٔ الف "
             "موقت است."),
    "D-20": ("وضعیت فعلی",
             "تا رسیدنِ دادهٔ مصالحِ پای‌کار تعیین نمی‌شود؛ گزینهٔ الف "
             "موقت است."),
}

# ── فاز E-10.1 §۱ — بازهٔ حساسیتِ واقعی (envelope) ──
# برای هر سنجه (ΔP / برآورد)، سناریوی کمینه و بیشینه با انتخابِ گزینه‌هایی
# که سنجه را در جهتِ دلخواه حرکت می‌دهند (از روی اندازه‌گیریِ فردیِ هر
# تصمیم) و سپس اجرای همزمانِ همهٔ آن‌ها ساخته می‌شود — جمع‌زدن ممنوع است.
# تصمیم‌های با اثرِ صفر در هیچ سناریویی چیزی را تغییر نمی‌دهند.
ENVELOPE = [
    {"id": "E-min-dp", "name": "کمینهٔ ΔP", "metric": "d_delta_p",
     "want_max": False},
    {"id": "E-max-dp", "name": "بیشینهٔ ΔP", "metric": "d_delta_p",
     "want_max": True},
    {"id": "E-min-bar", "name": "کمینهٔ برآورد", "metric": "d_baravord",
     "want_max": False},
    {"id": "E-max-bar", "name": "بیشینهٔ برآورد", "metric": "d_baravord",
     "want_max": True},
]

# variantهای فرضیِ کارِ جدید [FIX]: D-14 (فهرست پیمان) و D-15 (قیمت روز).
# توجه: D-15 و D-16 هر دو به یک تنظیمات (قیمت روز) ختم می‌شوند و فقط در
# مبنای مقایسه‌شان تفاوت دارند، پس یک variant نمایندهٔ هر دو است.
FIX_VARIANT_IDS = ("D-14", "D-15")


def envelope_overrides(payload, metric, want_max):
    """گزینه‌های extremum را از روی اندازه‌گیریِ فردی برمی‌گزیند.

    خروجی: (تنظیماتِ ترکیب‌شده، فهرستِ شناسه‌های انتخاب‌شده).
    """
    results = payload["results"]
    flips = {}
    chosen = []
    for sc in payload["scenarios"]:
        if sc["kind"] != "setting" or sc["id"] in FIX_IDS:
            continue
        d = (results.get(sc["id"]) or {}).get(metric)
        if d is None:
            continue
        if (want_max and d > 0) or (not want_max and d < 0):
            flips.update(sc["flip"])
            chosen.append(sc["id"])
    # گروهِ کارِ جدید [FIX]: فقط یک variant قابلِ اعمال است (تنظیماتِ مشترک)
    best_v, best_flip, best_id = None, None, None
    for fid in FIX_VARIANT_IDS:
        sc = next((x for x in payload["scenarios"] if x["id"] == fid), None)
        if sc is None:
            continue
        v = (results.get(fid) or {}).get(metric)
        if v is None:
            continue
        if best_v is None or (want_max and v > best_v) or \
                (not want_max and v < best_v):
            best_v, best_flip, best_id = v, sc["flip"], fid
    if best_v is not None and \
            ((want_max and best_v > 0.0) or (not want_max and best_v < 0.0)):
        flips.update(best_flip)
        chosen.append(best_id + " [FIX]")
    return flips, chosen


def main():
    payload = load_measured()
    base_m = payload["baseline_metrics"]
    results = payload["results"]

    print("سناریوهای ترکیبیِ جلسه اجرا می‌شوند ...")
    tables, map_df = build_inputs()
    scen_results = {}
    for s in SCENARIOS:
        scen_results[s["id"]] = run(tables, map_df, s["flips"])
        print("  %s done" % s["id"])
    scen_results["S3+D01"] = run(tables, map_df, D01_CONDITIONAL["flips"])
    print("  S3+D01 done")

    # ── فاز E-10.1 §۱ — بازهٔ حساسیت: چهار سناریوی اجرای همزمان ──
    envelope = {}
    for e in ENVELOPE:
        e_flips, e_chosen = envelope_overrides(payload, e["metric"],
                                               e["want_max"])
        e_m = run(tables, map_df, e_flips)
        envelope[e["id"]] = {
            "name": e["name"], "metric": e["metric"],
            "delta_p": e_m["delta_p"], "baravord": e_m["baravord"],
            "flips": e_chosen,
        }
        print("  %s done (%s)" % (e["id"], "، ".join(e_chosen)
                                  if e_chosen else "هیچ"))


    # ── ردیف‌های مرتب بر اساس max |اثر| ──
    scored = []
    for sc in payload["scenarios"]:
        res = results.get(sc["id"]) or {}
        if sc["kind"] in ("rejected", "merged"):
            continue
        mx = max_effect(res)
        scored.append((sc, res, mx))
    # sort: اثرِ عددیِ بیشتر اول؛ اثرِ صفر و نامشخص بعد
    scored.sort(key=lambda t: (t[2] is not None, t[2] or 0.0), reverse=True)
    rows = []
    for rank, (sc, res, mx) in enumerate(scored, 1):
        rows.append({
            "rank": rank, "id": sc["id"], "subject": sc["subject"],
            "option_a": sc.get("a", ""), "option_b": sc.get("b", ""),
            "max_effect": mx,
            "channels": effect_channels(res),
            "recommendation": RECOMMENDATIONS.get(sc["id"], "—"),
            "rec_source": REC_SOURCE.get(sc["id"], ("—", "")),
            "kind": sc["kind"],
        })
    # شکافِ رتبه‌بندی برای ردیف‌های بی‌اثر هم حفظ می‌شود (رتبهٔ یکتا)

    # ── مقادیرِ tornado (بدون سقفِ D-18 — مقیاسِ متفاوت) ──
    tor_vals = {}
    for sc in payload["scenarios"]:
        res = results.get(sc["id"]) or {}
        if sc["kind"] in ("rejected", "merged") or sc["id"] == "D-18":
            continue
        best = None
        for key, _label in CHANNELS:
            v = res.get(key)
            if v is not None and (best is None or abs(v) > abs(best)):
                best = v
        if best is None:
            continue
        tor_vals[sc["id"]] = best
    for r in rows:
        v = tor_vals.get(r["id"])
        if v is None:
            r["tornado_units"] = None
            r["tornado_neg"] = False
            r["tornado_val"] = 0.0
            continue
        r["tornado_val"] = abs(v)
        r["tornado_neg"] = v < 0
        r["tornado_units"] = abs(v)

    # ── خروجی‌ها ──

    # ── فاز E-10.1 §۱ — سناریوها و بازه در یک منبعِ واحد (آزمونِ T130) ──
    meeting_path = os.path.join(os.path.dirname(__file__),
                                "meeting_scenarios.json")
    with open(meeting_path, "w", encoding="utf-8") as fh:
        json.dump({
            "date": DATE, "rev_date": REV_DATE,
            "baseline": base_m,
            "scenarios": {s["id"]: scen_results[s["id"]] for s in SCENARIOS},
            "conditional_d01": scen_results["S3+D01"],
            "envelope": envelope,
        }, fh, ensure_ascii=False, indent=1)
    print("نوشته شد:", meeting_path)


    md = build_markdown(base_m, scen_results, rows, results, envelope)
    md_path = os.path.join(ROOT, "docs", "DECISION_MEETING.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md)
    print("نوشته شد:", md_path, len(md), "bytes")
    docx_path = os.path.join(ROOT, "docs", "DECISION_MEETING.docx")
    build_docx(docx_path, base_m, scen_results, rows, results, envelope)
    print("نوشته شد:", docx_path, os.path.getsize(docx_path), "bytes")

    # خلاصهٔ سریع برای کنسول
    print()
    for s in SCENARIOS:
        m = scen_results[s["id"]]
        print("  %s: ΔP = %.2f" % (s["id"], m["delta_p"]))
    print("  S3+D01: ΔP = %.2f" % scen_results["S3+D01"]["delta_p"])


if __name__ == "__main__":
    main()
