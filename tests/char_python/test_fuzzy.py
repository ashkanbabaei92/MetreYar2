import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import record
from app import fuzzy_match, conf_label


def _token_set_ratio_py(a, b):
    from app import _tokens, _quick_ratio
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    set_a, set_b = set(ta), set(tb)
    inter = sorted(set_a & set_b)
    s0 = " ".join(inter)
    s1 = " ".join(inter + sorted(set_a - set_b))
    s2 = " ".join(inter + sorted(set_b - set_a))
    return max(_quick_ratio(s0, s1), _quick_ratio(s0, s2), _quick_ratio(s1, s2))


def test_T37_fuzzy_identical():
    inputs = [("بتن", "بتن"), ("Concrete", "Concrete")]
    results = []
    for a, b in inputs:
        py = fuzzy_match(a, [b], threshold=0.3)
        results.append({"a": a, "b": b, "py_match": py[0], "py_score": py[1]})
    return record("T37", {"results": results}, generate=os.environ.get("GENERATE") == "1")


def test_T38_fuzzy_similar():
    inputs = [
        ("بتن مگر", "بتن‌مگر"),
        ("قلب بندی", "قالب‌بندی"),
        ("میلگرد", "آرماتور"),
    ]
    results = []
    for a, b in inputs:
        py = fuzzy_match(a, [b], threshold=0.3)
        tsr_py = _token_set_ratio_py(a, b)
        results.append({"a": a, "b": b, "py_match": py[0], "py_score": py[1],
                         "token_set_ratio": tsr_py})
    return record("T38", {"results": results}, generate=os.environ.get("GENERATE") == "1")


def test_conf_label():
    inputs = [0.95, 0.85, 0.70, 0.50, 0.99]
    results = {str(s): conf_label(s) for s in inputs}
    return record("conf_label", results, generate=os.environ.get("GENERATE") == "1")


if __name__ == "__main__":
    for fn in [test_T37_fuzzy_identical, test_T38_fuzzy_similar, test_conf_label]:
        print(fn.__name__, fn())