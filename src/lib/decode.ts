// ─────────────────────────────────────────────────────────────
// رمزگشایی بایت‌های فایل متنی با تشخیص خودکار انکودینگ
// معادل `decode_text` در app.py — زنجیرهٔ قطعی بدون وابستگی خارجی:
//   ۱) UTF-8 با BOM  (خروجی واقعی Revit)
//   ۲) UTF-8 بدون BOM (فهرست‌بها، فایل‌های Mapping)
//   ۳) Windows-1256   (خروجی Revit در ویندوز فارسی‌محور قدیمی)
// فایل‌های UTF-8 موجود هیچ تغییری در رفتار نمی‌بینند (بدون پس‌رفت).
// ─────────────────────────────────────────────────────────────

export function decodeText(bytes: Uint8Array): string {
  if (bytes.length >= 3 && bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf) {
    try {
      return new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(3));
    } catch {
      // BOM دارد ولی بدنه UTF-8 نیست؛ BOM را می‌کَنیم و ادامه می‌دهیم
      bytes = bytes.subarray(3);
    }
  }
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return new TextDecoder("windows-1256").decode(bytes);
  }
}
