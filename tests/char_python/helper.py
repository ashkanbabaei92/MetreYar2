import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")


def load_fixture(*path_parts):
    path = os.path.join(FIXTURES_DIR, *path_parts)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_json_fixture(*path_parts):
    path = os.path.join(FIXTURES_DIR, *path_parts)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filename, output_dir=None):
    target = output_dir or OUTPUT_DIR
    os.makedirs(target, exist_ok=True)
    path = os.path.join(target, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def golden_path(test_id):
    return os.path.join(GOLDEN_DIR, f"{test_id}.json")


def record(test_id, data, generate=False):
    gp = golden_path(test_id)
    # ساختن/بازنویسی golden فقط با پرچم صریح مجاز است. بدون پرچم،
    # golden مفقود باید تست را FAIL کند تا رگرسیون‌ها پنهان نمانند.
    allow_create = generate or os.environ.get("UPDATE_GOLDENS") == "1"
    if not os.path.exists(gp):
        if not allow_create:
            raise AssertionError(
                f"golden مفقود: «{gp}». اگر این رفتار جدید و مورد انتظار است، "
                f"آن را با GENERATE=1 یا UPDATE_GOLDENS=1 بسازید. ساختن خاموش "
                f"golden ممنوع است (رگرسیون پنهان می‌شود).")
        save_json(data, f"{test_id}.json", GOLDEN_DIR)
        return {"status": "golden_created", "path": gp}
    if generate:
        # بازنویسی صریح golden موجود (تولید دوبارهٔ عمدی)
        save_json(data, f"{test_id}.json", GOLDEN_DIR)
        return {"status": "golden_updated", "path": gp}
    existing = load_json(gp)
    return {"status": "compare", "golden": existing, "actual": data}


def assert_golden(test_id, data, generate=False):
    res = record(test_id, data, generate=generate)
    if res["status"] == "compare":
        # Round-trip through JSON with default=str so tuple/float types match golden JSON representation
        normalized_actual = json.loads(json.dumps(data, ensure_ascii=False, default=str))
        assert normalized_actual == res["golden"], f"{test_id} golden mismatch"
    return res


def json_default(obj):
    return str(obj)