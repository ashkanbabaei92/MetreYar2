# -*- coding: utf-8 -*-
# T131 — بازتولیدپذیریِ منابعِ رسمی (فاز E-10.1 §۲).
#
# docs/sources/BULLETINS_MANIFEST.md هر PDF رسمی را با sha256 ثبت می‌کند و
# tools/verify_bulletins.py قبل از هر تطبیقی آن‌ها را چک می‌کند. این آزمون:
#   ۱) هر PDF در docs/sources/bulletins در مانیفست هست (نه کم، نه زیاد)؛
#   ۲) sha256 هر فایل با مانیفست هم‌خوان است؛
#   ۳) جدولِ .md با MANIFESTِ ابزار هم‌خوان است (یک منبع، نه دو تا)؛
#   ۴) فایلِ مفقود یا هشِ نامطبابق → خطای صریح.
import io
import os
import re
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
BULL = os.path.join(ROOT, "docs", "sources", "bulletins")
MD = os.path.join(ROOT, "docs", "sources", "BULLETINS_MANIFEST.md")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from verify_bulletins import MANIFEST, _sha256, verify_hashes  # noqa: E402

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def _skip_if_pdfs_missing():
    if not os.path.exists(os.path.join(BULL, "Tadil1404-34.pdf")):
        pytest.skip("PDF بخشنامه موجود نیست (docs/sources/bulletins git-track نمی‌شود)")


def _walk_pdfs(base):
    out = []
    for dp, dirs, files in os.walk(base):
        for fn in sorted(files):
            if fn.lower().endswith(".pdf"):
                rel = os.path.relpath(os.path.join(dp, fn), base)
                out.append(rel.replace("\\", "/"))
    return out


def test_T131_manifest_covers_every_pdf():
    """هر PDF روی دیسک باید دقیقاً در مانیفست باشد."""
    on_disk = set(_walk_pdfs(BULL))
    listed = set(MANIFEST)
    assert on_disk == listed, (
        "فقط در دیسک: %s | فقط در مانیفست: %s" % (sorted(on_disk ^ listed),
                                                  sorted(on_disk ^ listed)))


def test_T131_hashes_match_files():
    """sha256 همهٔ فایل‌ها با مانیفست هم‌خوان باشد."""
    errs = verify_hashes()
    assert errs == [], "\n".join(errs)


def test_T131_md_table_matches_tool_manifest():
    """جدولِ مانیفستِ .md باید با MANIFESTِ ابزار یک‌به‌یک هم‌خوان باشد."""
    t = io.open(MD, encoding="utf-8").read()
    got = {}
    for ln in t.splitlines():
        m_path = re.match(r"^\|\s*`([^`]+)`", ln)
        m_hash = re.search(r"`([0-9a-f]{64})`", ln)
        if m_path and m_hash:
            got[m_path.group(1)] = m_hash.group(1)
    assert got == MANIFEST, (
        "فقط در .md: %s | فقط در ابزار: %s"
        % (sorted(set(got) ^ set(MANIFEST)), sorted(set(got) ^ set(MANIFEST))))


def test_T131_missing_file_is_an_explicit_error():
    """فایلِ مفقود باید خطای صریح بدهد (نه crash)."""
    errs = verify_hashes(manifest={"missing.pdf": "00" * 32}, base_dir=BULL)
    assert len(errs) == 1
    assert "فایل مفقود" in errs[0]


def test_T131_wrong_hash_is_an_explicit_error():
    """هشِ نامطبابق باید خطای صریح بدهد و مقدارِ واقعی را نشان دهد."""
    good = "Tadil1404-34.pdf"
    real = _sha256(os.path.join(BULL, good))
    wrong = "0" * 64
    assert wrong != real
    errs = verify_hashes(manifest={good: wrong}, base_dir=BULL)
    assert len(errs) == 1
    assert "نامطبابق" in errs[0]
    # مقدارِ درست در پیام هست تا کاربر بداند چه چیزی تغییر کرده
    assert real in errs[0]
