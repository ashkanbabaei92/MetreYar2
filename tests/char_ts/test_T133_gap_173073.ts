// ─────────────────────────────────────────────────────────────
// T133 — شکافِ ۲۰۸۰ → ۱۷۳۰۷۳ (فاز E-11-A).
// (آینهٔ test_T133_gap_173073.py — پاریتیِ py↔ts)
//
// این آزمون‌ها شکاف‌های مستندشده در docs/COMPLIANCE_2080_vs_173073.md را
// به‌صورتِ ماشینی قفل می‌کنند. در فاز E-11-A هنوز پیاده نشده‌اند، پس دو
// آزمون it.fails (انتظارِ شکست) و یکی it.skip است. وقتی در فاز E-11-B
// پیاده شوند، it.failsها سبز می‌شوند — دقیقاً مثلِ T111.
//
//   ۱) گردکردن ۴→۳ رقم (۱۷۳۰۷۳ ۵-۳ در برابر ۲۰۸۰ ۸-۲)  → it.fails
//   ۲) طبقهٔ سومِ k = ۰٫۹۷۵ (۱۷۳۰۷۳ ۸-۲)                  → it.fails
//   ۳) بخشِ bulletin_173073 در config                     → it.skip (داده)
//   ۴) خودِ فایلِ تحلیل موجود و کامل است                   → سبز (همین)
// ─────────────────────────────────────────────────────────────
import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { defaultSettings } from "../../src/lib/engine";
import { roundCoef2080, tadilK } from "../../src/lib/adjustment";

const ROOT = path.join(__dirname, "..", "..");
const CONFIG = path.join(ROOT, "config", "index_bulletins.json");
const COMPLIANCE = path.join(ROOT, "docs", "COMPLIANCE_2080_vs_173073.md");

// ── ۱) ۱۷۳۰۷۳ بند ۵-۳: ضریب ابتدا با ۴ رقم اعشار محاسبه، سپس به ۳ رقم
// گرد می‌شود. ۲۰۸۰ بند ۸-۲: ۳ رقم → ۲ رقم. اعداد از probes واقعی موتور.
describe.each([
  { raw: 0.1235, expected: 0.124 }, // رقم چهارم (=۵) ⇒ حذف و یک واحد به رقم سوم
  { raw: 0.1234, expected: 0.123 }, // رقم چهارم (<۵) ⇒ حذف
])("T133 گردکردن ۴→۳ رقم", ({ raw, expected }) => {
  it.fails("تحت ۱۷۳۰۷۳ بند ۵-۳ ضریب به ۳ رقم گرد می‌شود، نه ۲", () => {
    // xfailِ فعلی: ۲۰۸۰ ۸-۲ (۲ رقم) — COMPLIANCE §۲-۷ / D-03
    expect(roundCoef2080(raw)).toBeCloseTo(expected, 10);
  });
});

// ── ۲) ۱۷۳۰۷۳ بندهای ۸-۱/۸-۲: سه طبقه. ۲۰۸۰ فقط دو طبقه دارد.
// «extended» = حالتِ سومِ پیشنهادی (اتمام در مدتِ اولیه + تأخیرهای مجاز).
describe("T133 طبقهٔ سومِ k", () => {
  it.fails("k = ۰٫۹۷۵ برای اتمام در مدتِ اولیه + تأخیر مجاز", () => {
    // xfailِ فعلی: چنین حالتی وجود ندارد — COMPLIANCE §۲-۱ / D-01
    const s = {
      ...defaultSettings(),
      completedWithinTerm: "extended" as unknown as boolean,
    };
    expect(tadilK(s)[0]).toBeCloseTo(0.975, 10);
  });
});

// ── ۳) بخشِ bulletin_173073 هنوز در config نیست.
describe("T133 بخشِ config", () => {
  it.skip("bulletin_173073 باید به config اضافه شود", () => {
    // skip تا فاز E-11-B ۳-۲ — نیازمندِ ثبتِ هش و مسیرِ neu/101-173073.pdf
    const cfg = JSON.parse(fs.readFileSync(CONFIG, "utf-8")) as Record<
      string,
      unknown
    >;
    expect("bulletin_173073" in cfg).toBe(true);
  });
});

// ── ۴) خودِ تحلیلِ شکاف موجود است (این یکی سبز است).
describe("T133 سندِ تحلیل", () => {
  it("فایلِ COMPLIANCE بخش‌های §۲ و §۶ و بندهای کلیدی را دارد", () => {
    const text = fs.readFileSync(COMPLIANCE, "utf-8");
    expect(text).toContain("## ۲. ۱۱ موردِ پرخطر");
    expect(text).toContain("## ۶. برنامهٔ فاز E-11-B");
    for (const token of ["۰٫۹۷۵", "۵-۳", "۱-۸-۱", "۲-۱-۵-۲"]) {
      expect(text).toContain(token);
    }
  });
});
