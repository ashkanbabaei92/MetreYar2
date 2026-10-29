import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import assert_golden, record
from app import convert_persian_digits


def test_T06_T13_number_all():
    inputs = ["12.50", "12,50", "1,250.75", "1.250,75", "۱۲٫۵۰", "12٬500", "1.250", " 12.50 "]
    results = {}
    for inp in inputs:
        converted = convert_persian_digits(inp)
        results[inp] = {"original": inp, "persian_digits_converted": converted}
    assert_golden("T06_T13_numbers", {"inputs": results},
                  generate=os.environ.get("GENERATE") == "1")


if __name__ == "__main__":
    print(test_T06_T13_number_all())