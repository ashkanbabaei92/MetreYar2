import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import assert_golden, record
from app import rebar_unit_weight, REBAR_UNIT_WEIGHT, TechnicalOfficeEngine

# کد ریزمترهٔ آرماتور بر اساس آستانهٔ قطر (mm): ≤10 → 070201 ، ۱۲–۱۸ → 070202 ، ≥۲۰ → 070203
def bucket_of(diameter_mm: float, grade: str = "IR-Rebar-Fy4000") -> str:
    return TechnicalOfficeEngine._rebar_bucket(diameter_mm, grade)


def test_T20_rebar_phi8():
    assert_golden("T20", {"input": 8, "weight": rebar_unit_weight(8),
                          "table_value": REBAR_UNIT_WEIGHT.get(8)},
                  generate=os.environ.get("GENERATE") == "1")


def test_T21_rebar_phi14():
    assert_golden("T21", {"input": 14, "weight": rebar_unit_weight(14),
                          "table_value": REBAR_UNIT_WEIGHT.get(14)},
                  generate=os.environ.get("GENERATE") == "1")


def test_T22_rebar_phi25():
    assert_golden("T22", {"input": 25, "weight": rebar_unit_weight(25),
                          "table_value": REBAR_UNIT_WEIGHT.get(25)},
                  generate=os.environ.get("GENERATE") == "1")


def test_T23_rebar_phi36():
    assert_golden("T23", {"input": 36, "weight": rebar_unit_weight(36),
                          "table_value": REBAR_UNIT_WEIGHT.get(36)},
                  generate=os.environ.get("GENERATE") == "1")


def test_T24_rebar_bucket_boundary_mm():
    """آستانه‌های قطر آرماتور بر حسب میلی‌متر."""
    assert bucket_of(10) == "070201"
    assert bucket_of(10.01) == "070202"
    assert bucket_of(18) == "070202"
    assert bucket_of(18.01) == "070203"
    assert bucket_of(25) == "070203"


def test_T25_rebar_bucket_boundary_meters():
    """ستون «Bar Diameter» پس از to_si بر حسب متر است (۰.۰۱۸)؛ باید مانند mm رفتار کند."""
    assert bucket_of(0.010) == "070201"     # Φ10
    assert bucket_of(0.01001) == "070202"   # کمی بیش از ۱۰ mm
    assert bucket_of(0.018) == "070202"     # Φ18
    assert bucket_of(0.01801) == "070203"   # کمی بیش از ۱۸ mm
    assert bucket_of(0.025) == "070203"     # Φ25


def test_T26_rebar_bucket_plain_grade():
    """گرید ساده (AI/2400) مستقل از قطر → 070101."""
    assert bucket_of(8, "IR-Rebar-Fy2400") == "070101"
    assert bucket_of(0.020, "IR-Rebar-Fy2400") == "070101"


if __name__ == "__main__":
    for fn in [test_T20_rebar_phi8, test_T21_rebar_phi14, test_T22_rebar_phi25, test_T23_rebar_phi36]:
        print(fn.__name__, fn())