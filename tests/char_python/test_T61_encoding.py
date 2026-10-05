# -*- coding: utf-8 -*-
# T61 - پشتیبانی از انکودینگ‌های غیر UTF-8 (مرحلهٔ ۳)
#
# زنجیرهٔ رمزگشایی `decode_text`: UTF-8-BOM → UTF-8 → Windows-1256.
# هیچ فایل ورودی واقعی پروژه غیر از UTF-8 نیست (همهٔ خروجی‌های Revit
# UTF-8-BOM و فهرست‌بها UTF-8)، ولی خروجی Revit در ویندوز فارسی‌محورِ قدیمی
# می‌تواند cp1256 باشد؛ این تست آن مسیر را پوشش می‌دهد.
#
# fixture با محاسبهٔ واقعی تولید شده (اسکریپت gen_enc_fixture) و در
# char_shared قرار دارد تا سمت TS دقیقاً همان بایت‌ها را ببیند.
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app import decode_text, normalize_text  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "char_shared",
                       "fixtures", "encoding_samples.json")


def _samples():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


def test_T61_utf8():
    for s in _samples():
        assert decode_text(bytes.fromhex(s["utf8_hex"])) == s["text"]


def test_T61_utf8_bom():
    for s in _samples():
        assert decode_text(bytes.fromhex(s["utf8_bom_hex"])) == s["text"]


def test_T61_windows1256():
    # ی فارسی در cp1256 با ی عربی (U+064A) ذخیره می‌شود
    for s in _samples():
        assert decode_text(bytes.fromhex(s["cp1256_hex"])) == s["text_cp1256"]


def test_T61_cp1256_normalizes_identically():
    """فایل cp1256 بعد از normalize با فایل UTF-8 یکسان می‌شود."""
    for s in _samples():
        raw_cp1256 = bytes.fromhex(s["cp1256_hex"])
        assert normalize_text(decode_text(raw_cp1256)) == normalize_text(s["text"])


def test_T61_dynamic_roundtrip():
    """cross-check فیكسچر با انکود واقعی پایتون (نه مقادیر ذخیره‌شده)."""
    for s in _samples():
        text = s["text"]
        assert decode_text(text.encode("utf-8")) == text
        assert decode_text(b"\xef\xbb\xbf" + text.encode("utf-8")) == text
        assert decode_text(s["text_cp1256"].encode("windows-1256")) == s["text_cp1256"]


if __name__ == "__main__":
    for fn in [test_T61_utf8, test_T61_utf8_bom, test_T61_windows1256,
               test_T61_cp1256_normalizes_identically, test_T61_dynamic_roundtrip]:
        fn()
        print(fn.__name__, "ok")
