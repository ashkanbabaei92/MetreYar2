import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from helper import record
from app import parse_value_unit, to_si


def test_T06_number_12_50():
    result_py = parse_value_unit("12.50")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T06", {"input": "12.50", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


def test_T07_number_12_50():
    result_py = parse_value_unit("12,50")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T07", {"input": "12,50", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


def test_T08_number_1250_75():
    result_py = parse_value_unit("1,250.75")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T08", {"input": "1,250.75", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


def test_T09_number_1250_75_eu():
    result_py = parse_value_unit("1.250,75")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T09", {"input": "1.250,75", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


def test_T10_number_persian():
    result_py = parse_value_unit("۱۲٫۵۰")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T10", {"input": "۱۲٫۵۰", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


def test_T11_number_arabic_thousands():
    result_py = parse_value_unit("12٬500")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T11", {"input": "12٬500", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


def test_T12_number_ambiguous():
    result_py = parse_value_unit("1.250")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T12", {"input": "1.250", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


def test_T13_number_whitespace():
    result_py = parse_value_unit(" 12.50 ")
    result_si = to_si(result_py[0], result_py[1]) if result_py else None
    return record("T13", {"input": " 12.50 ", "parse": result_py, "si": result_si},
                  generate=os.environ.get("GENERATE") == "1")


if __name__ == "__main__":
    for fn in [test_T06_number_12_50, test_T07_number_12_50, test_T08_number_1250_75,
               test_T09_number_1250_75_eu, test_T10_number_persian, test_T11_number_arabic_thousands,
               test_T12_number_ambiguous, test_T13_number_whitespace]:
        print(fn.__name__, fn())