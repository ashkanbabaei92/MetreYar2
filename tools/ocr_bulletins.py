# -*- coding: utf-8 -*-
"""tools/ocr_bulletins.py — فاز E-11-A §۰.

استخراجِ متنِ اسکن‌های رسمیِ بخشنامه‌ها (که لایهٔ متن ندارند) با OCR.

  python tools/ocr_bulletins.py --pdf docs/sources/bulletins/neu/101-173073.pdf
  python tools/ocr_bulletins.py --pdf .../101-173073.pdf --zoom 3 --out x.txt

روش: هر صفحه با PyMuPDF رندر می‌شود و با easyocr (مدلِ فارسی) خوانده
می‌شود. خروجی، متنِ صفحه‌به‌صفحه است.

⚠ **وابستگیِ اختیاری:** این ابزار `easyocr` و `pymupdf` نیاز دارد که
بخشی از وابستگی‌های اصلیِ پروژه نیستند. موتورِ برنامه و آزمون‌ها **هرگز**
به این ابزار وابسته نیستند؛ فقط بازتولیدپذیریِ مستندات است.

⚠ **خروجیِ OCR منبعِ قانونی نیست.** مرجعِ رسمی خودِ PDF است (با sha256 در
docs/sources/BULLETINS_MANIFEST.md). هر نقلِ قولی که از این خروجی گرفته
می‌شود، در صورتِ ابهام باید با خواندنِ دستیِ اسکن تأیید شود.
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def render(pdf_path, zoom, out_path):
    import fitz  # noqa: PLC0415
    d = fitz.open(pdf_path)
    lines = []
    for pi in range(d.page_count):
        img = os.path.join(os.path.dirname(out_path) or ".",
                           ".ocr_tmp_p%02d.png" % (pi + 1))
        d[pi].get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(img)
        res = _read(img)
        os.remove(img)
        print("صفحهٔ %d: %d خط" % (pi + 1, len(res)), flush=True)
        lines.append("===== PAGE %d =====" % (pi + 1))
        lines.extend(res)
    text = "\n".join(lines) + "\n"
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("نوشته شد: %s (%d کاراکتر)" % (out_path, len(text)))


def _read(img):
    from easyocr import Reader  # noqa: PLC0415
    global _READER
    try:
        _READER
    except NameError:
        _READER = Reader(["fa"], gpu=False)
    return _READER.readtext(img, detail=0, paragraph=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pdf", required=True, help="مسیرِ فایلِ PDF اسکن‌شده")
    ap.add_argument("--out", help="فایلِ خروجی (پیش‌فرض: stdout نشان داده نمی‌شود)")
    ap.add_argument("--zoom", type=float, default=3.0,
                    help="مقیاقِ رندر (پیش‌فرض ۳؛ برای فرمول‌ها ۵-۱۳)")
    args = ap.parse_args()
    if not os.path.exists(args.pdf):
        sys.exit("PDF پیدا نشد: %s" % args.pdf)
    out = args.out or os.path.join(
        os.path.dirname(args.pdf) or ".",
        os.path.splitext(os.path.basename(args.pdf))[0] + "_ocr.txt")
    render(args.pdf, args.zoom, out)


if __name__ == "__main__":
    main()
