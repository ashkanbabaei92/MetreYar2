import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import record
from app import normalize_text, convert_persian_digits, to_si, chapter_title, fuzzy_match, conf_label


def test_T24_kind_classification():
    from app import RevitScheduleParser
    results = {}
    for kind, title in [("lean_concrete", "جدول ریزمتره بتن مگر"),
                         ("structural_concrete", "جدول ریزمتره حجم بتن سازه‌ای"),
                         ("formwork_foundation", "جدول قالب‌بندی پی"),
                         ("joist_floor", "سقف تیرچه بلوک")]:
        _, conf = RevitScheduleParser._classify(title, ["mark", "volume"])
        results[kind] = {"kind": kind, "confidence": conf}
    return record("T24", results, generate=os.environ.get("GENERATE") == "1")


def test_T54_normalize_zwnj_classification():
    """U+200C (نیم‌فاصله) must normalize to a space so the classifier rules match."""
    from app import RevitScheduleParser
    assert normalize_text("حجم بتن سازه‌ای") == normalize_text("حجم بتن سازه ای")
    assert normalize_text("قالب‌بندی سازه") == normalize_text("قالب بندی سازه")
    assert RevitScheduleParser._classify("جدول ریزمتره حجم بتن سازه‌ای",
                                         ["mark", "volume"]) == ("structural_concrete", 0.97)
    assert RevitScheduleParser._classify("جدول ریزمتره قالب‌بندی سازه",
                                         ["mark", "area"]) == ("formwork_super", 0.95)
    # شکاف‌های تأییدشده: «اسکلت» و «بتن‌ریزی پی» هم باید با قاعدهٔ عنوان تشخیص داده شوند
    assert normalize_text("قالب‌بندی اسکلت") == normalize_text("قالب بندی اسکلت")
    assert normalize_text("بتن‌ریزی پی") == normalize_text("بتن ریزی پی")
    assert RevitScheduleParser._classify("جدول ریزمتره قالب‌بندی اسکلت",
                                         ["category", "area"]) == ("formwork_super", 0.95)
    assert RevitScheduleParser._classify("جدول بتن‌ریزی پی",
                                         ["mark", "length", "volume", "area"]) == ("structural_concrete", 0.97)


def test_T25_si_mm_to_m():
    result = to_si(1000.0, "mm")
    return record("T25", {"input": (1000.0, "mm"), "result": result},
                  generate=os.environ.get("GENERATE") == "1")


def test_T26_si_cm_to_m():
    result = to_si(100.0, "cm")
    return record("T26", {"input": (100.0, "cm"), "result": result},
                  generate=os.environ.get("GENERATE") == "1")


def test_T27_si_ton_to_kg():
    result = to_si(1.0, "ton")
    return record("T27", {"input": (1.0, "ton"), "result": result},
                  generate=os.environ.get("GENERATE") == "1")


def test_T28_persian_digits():
    inputs = ["۱۲٫۵۰", "۱۲۳", "۰"]
    results = {}
    for inp in inputs:
        results[inp] = {
            "to_en": convert_persian_digits(inp),
            "normalize": normalize_text(inp),
        }
    return record("T28", results, generate=os.environ.get("GENERATE") == "1")


def test_T29_normalize_stop_words():
    inputs = ["و بتن و سازه به در", "سقف تیرچه بلوک"]
    results = {}
    for inp in inputs:
        tokens = [t for t in normalize_text(inp).split() if t and t not in
                  {"و", "به", "از", "در", "با", "برای", "هر", "نوع", "تا", "مورد"}]
        results[inp] = {"normalized": normalize_text(inp), "tokens": tokens}
    return record("T29", results, generate=os.environ.get("GENERATE") == "1")


def test_T30_normalize_arabic():
    inputs = ["کلمات عربی كي تبديل ميشن", "إلى أبتداء"]
    results = {}
    for inp in inputs:
        results[inp] = {"original": inp, "normalized": normalize_text(inp),
                        "persian": convert_persian_digits(inp)}
    return record("T30", results, generate=os.environ.get("GENERATE") == "1")


if __name__ == "__main__":
    for fn in [test_T24_kind_classification, test_T54_normalize_zwnj_classification,
               test_T25_si_mm_to_m, test_T26_si_cm_to_m,
               test_T27_si_ton_to_kg, test_T28_persian_digits, test_T29_normalize_stop_words,
               test_T30_normalize_arabic]:
        print(fn.__name__, fn())