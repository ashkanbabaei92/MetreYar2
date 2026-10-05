# -*- coding: utf-8 -*-
# T123 — فاز E-9 §۶: ابزارِ واردکردنِ شاخص‌های بخشنامهٔ جدید.
#
# اعتبارسنجیِ ابزارِ tools/import_bulletin.py: تکرار، پرشِ >۳۰٪،
# سه‌ماههٔ غایب، و ساختارِ خروجیِ build_patched. مسیرِ سنگینِ
# «گزارشِ اثر» (اجرای خطِ لولهٔ مرجع) در اینجا اجرا نمی‌شود — در حالتِ
# تعاملیِ ابزار با دادهٔ واقعی دیده می‌شود.
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.abspath(ROOT))

import importlib.util  # noqa: E402

_TOOL = os.path.join(ROOT, "tools", "import_bulletin.py")
_SPEC = importlib.util.spec_from_file_location("import_bulletin", _TOOL)
ib = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ib)

CONFIG_PATH = os.path.join(ROOT, "config", "index_bulletins.json")


def _cfg():
    with open(CONFIG_PATH, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def _good(overrides=None):
    data = {"bulletin": "بخشنامه ۱۴۰۵/۱۴۵۶۷۸",
            "bulletin_date": "۱۴۰۵/۰۷/۰۱",
            "quarter": "1405Q1", "kind": "disciplines",
            "rows": [{"name": "ابنیه", "q1_1405": 16000.0, "page": 4},
                     {"name": "تاسیسات مکانیکی", "q1_1405": 19000.0,
                      "page": 4}]}
    if overrides:
        data.update(overrides)
    return data


# ═════════ ساختار و فیلدهای الزامی ═════════

@pytest.mark.parametrize("missing", ["bulletin", "quarter", "kind", "rows"])
def test_T123_missing_required_field(missing):
    data = _good()
    data.pop(missing)
    errs, _w = ib.validate(data, _cfg())
    assert any("الزامی" in e for e in errs)


def test_T123_bad_quarter():
    errs, _w = ib.validate(_good({"quarter": "1406Q1"}), _cfg())
    assert any("نامعتبر" in e for e in errs)


def test_T123_bad_kind():
    errs, _w = ib.validate(_good({"kind": "widgets"}), _cfg())
    assert any("نوعِ نامعتبر" in e for e in errs)


# ═════════ ۳) سه‌ماههٔ غایب ═════════

def test_T123_missing_season_value():
    data = _good({"rows": [{"name": "ابنیه", "q1_1405": 16000.0},
                           {"name": "تاسیسات مکانیکی", "page": 4}]})
    errs, _w = ib.validate(data, _cfg())
    assert any("سه‌ماههٔ غایب" in e for e in errs)


def test_T123_nonpositive_value():
    errs, _w = ib.validate(_good({"rows": [{"name": "ابنیه",
                                            "q1_1405": 0.0}]}), _cfg())
    assert any("مثبت" in e for e in errs)


def test_T123_chapter_must_be_numeric():
    errs, _w = ib.validate(_good({"kind": "chapters_abnieh",
                                  "rows": [{"chapter": "۶",
                                            "q1_1405": 100.0}]}), _cfg())
    assert not errs  # «۶» عددی است

    errs, _w = ib.validate(_good({"kind": "chapters_abnieh",
                                  "rows": [{"chapter": "شش",
                                            "q1_1405": 100.0}]}), _cfg())
    assert any("عددی نیست" in e for e in errs)


# ═════════ ۱) تکرار ═════════

def test_T123_duplicate_bulletin_detected():
    cfg = _cfg()
    # شمارهٔ ۱۵۵۲۳۳ در meta.bulletin هست
    data = _good({"bulletin": "بخشنامه ۱۴۰۵/۱۵۵۲۳۳"})
    errs, _w = ib.validate(data, cfg)
    assert any("تکرار" in e for e in errs)


def test_T123_new_bulletin_not_duplicate():
    errs, _w = ib.validate(_good({"bulletin": "بخشنامه ۱۴۰۵/۱۴۹۹۹۹"}),
                           _cfg())
    assert not [e for e in errs if "تکرار" in e]


def test_T123_import_log_blocks_second_import():
    """ورودیِ اول اعمال شود؛ دفعهٔ بعد همان بخشنامه تکرار می‌خورد."""
    cfg = ib.build_patched(_cfg(), _good())
    errs, _w = ib.validate(_good(), cfg)
    assert any("تکرار" in e for e in errs)


# ═════════ ۲) پرشِ >۳۰٪ ═════════

def test_T123_jump_warns():
    # ابنیه q4_1404 = ۱۴۳۳۳٫۱ ؛ ۳۰۰۰۰ یعنی +۱۰۹٪
    data = _good({"rows": [{"name": "ابنیه", "q1_1405": 30000.0},
                           {"name": "تاسیسات مکانیکی",
                            "q1_1405": 19000.0}]})
    errs, warns = ib.validate(data, _cfg())
    assert not errs
    assert any("پرشِ بزرگ" in w and "ابنیه" in w for w in warns)


def test_T123_small_jump_no_warning():
    # ابنیه q4_1404 = ۱۴۳۳۳٫۱ ؛ ۱۵۰۰۰ یعنی +۴٫۶٪
    errs, warns = ib.validate(_good(), _cfg())
    assert not errs
    assert not [w for w in warns if "پرش" in w]


# ═════════ ساختارِ خروجی ═════════

def test_T123_build_patched_structure():
    cfg = ib.build_patched(_cfg(), _good())
    d = cfg["definitive_1405"]
    assert d["quarters"]["1405Q1"]["announced"] is True
    assert "۱۴۵۶۷۸" in d["quarters"]["1405Q1"]["source"]
    assert d["status"].startswith("واردشده")
    names = [r["name"] for r in d["disciplines"]]
    assert "ابنیه" in names and "تاسیسات مکانیکی" in names
    assert len(d["import_log"]) == 1
    assert d["import_log"][0]["quarter"] == "1405Q1"
    src = cfg["index_sources"]["periods"]["q1_1405"]
    assert src["type"] == "قطعی" and src["bulletin_no"] == "۱۴۵۶۷۸"


def test_T123_build_patched_merges_existing_rows():
    """واردکردنِ دوم ردیفِ موجود را به‌روز می‌کند، نه اینکه تکرار کند."""
    cfg = ib.build_patched(_cfg(), _good())
    cfg = ib.build_patched(cfg, _good({"bulletin": "بخشنامه ۱۴۰۵/۱۴۹۹۹۹",
                                       "rows": [{"name": "ابنیه",
                                                 "q1_1405": 17000.0}]}))
    names = [r["name"] for r in cfg["definitive_1405"]["disciplines"]]
    assert names.count("ابنیه") == 1
    row = [r for r in cfg["definitive_1405"]["disciplines"]
           if r["name"] == "ابنیه"][0]
    assert row["q1_1405"] == 17000.0


def test_T123_write_config_roundtrip(tmp_path):
    cfg = ib.build_patched(_cfg(), _good())
    p = str(tmp_path / "index_bulletins.json")
    ib.write_config(p, cfg)
    raw = open(p, "rb").read()
    assert raw.count(b"\r\n") > 0
    assert raw.count(b"\n") == raw.count(b"\r\n")  # هیچ LFِ تنها
    assert raw.endswith(b"\r\n")
    # قالبِ پروندهٔ اصلی حفظ شود (indent=2) تا diff تمیز بماند
    lines = raw.split(b"\r\n")
    assert lines[1] == b'  "meta": {', lines[1]
    back = json.loads(raw.decode("utf-8"))
    assert back["definitive_1405"]["quarters"]["1405Q1"]["announced"] is True


# ═════════ CLI در حالتِ خشک ═════════

def test_T123_cli_dry_run_does_not_write():
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "t123_input.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_good(), fh, ensure_ascii=False)
    before = open(CONFIG_PATH, "rb").read()
    p = subprocess.run([sys.executable, _TOOL, "--input", tmp,
                        "--no-impact"], capture_output=True,
                       cwd=os.path.abspath(ROOT), env=env)
    assert p.returncode == 0
    assert open(CONFIG_PATH, "rb").read() == before  # دست‌نخورده


def test_T123_cli_errors_exit_nonzero():
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "t123_bad.json")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(_good({"quarter": "1406Q1"}), fh, ensure_ascii=False)
    p = subprocess.run([sys.executable, _TOOL, "--input", tmp,
                        "--no-impact"], capture_output=True,
                       cwd=os.path.abspath(ROOT), env=env)
    assert p.returncode == 1
    assert b"\xd9\x86\xd8\xa7\xd9\x85\xd8\xb9\xd8\xaa\xd8\xa8\xd8\xb1" in p.stdout  # «نامعتبر»


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
