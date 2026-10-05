import { describe, it, expect, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

// ── T08: engine parity تکی — هر ۱۰ فایل واقعی جداگانه به computeProject ──
// مقادیر مورد انتظار از خروجی TechnicalOfficeEngine.compute در app.py روی
// همین فایل‌ها گرفته شده‌اند (هر جدول به‌تنهایی، map_df=None) و پس از
// بازنگاشت مرحلهٔ ۲ با پایگاه فهرست‌بهای واقعی ۱۴۰۴ به‌روزرسانی شده‌اند.
// پی و پله هر دو ۰۸۰۱۰۵ هستند ولی ردیف‌های جداگانه‌اند.
// مرحلهٔ ۱۱: ضریب پرت حذف شد (qty تنها کمیت است)؛
// grand = base × ۱٫۳ (بالاسری) × ۱٫۰۴ (منطقه‌ای — ایراد ۴،
// گلستان/گرگان/مرکزی/ابنیه) × ۱ (طبقات — ایراد ۳، ناقص) + ۰ (تجهیز) —
// map_df=None.

interface ExpectLine {
  code: string;
  qty: number;
}

interface ExpectFile {
  lines: ExpectLine[];
  baseTotal: number;
  grandTotal: number;
}

const EXPECTED: ExpectFile[] = [
  // ۰) جدول بتن‌ریزی پی - Foundation Concrete
  {
    lines: [
      { code: "080105", qty: 152.83 },
    ],
    baseTotal: 2985534050.0000005,
    grandTotal: 4036442035.6000013,
  },
  // ۱) جدول ریزمتره آرماتورها - Structural Rebar
  {
    lines: [
      { code: "070101", qty: 125.57 },
      { code: "070201", qty: 308.79 },
      { code: "070202", qty: 11385.000000000007 },
      { code: "070203", qty: 284.1 },
      { code: "280101", qty: 242.06920000000014 },
    ],
    baseTotal: 4576880540.280003,
    grandTotal: 6187942490.458564,
  },
  // ۲) جدول ریزمتره آرماتورهای اتصال تیرچه - Joist Connection Rebar
  {
    lines: [
      { code: "070202", qty: 99.43 },
      { code: "280101", qty: 1.9886000000000001 },
    ],
    baseTotal: 37392441.24,
    grandTotal: 50554580.556480005,
  },
  // ۳) جدول ریزمتره آرماتورهای تیرچه - Joist Rebar
  {
    lines: [
      { code: "070201", qty: 267.188837 },
      { code: "070202", qty: 66.125303 },
      { code: "280101", qty: 6.6662827999999985 },
    ],
    baseTotal: 142983245.24352,
    grandTotal: 193313347.56923905,
  },
  // ۴) جدول ریزمتره بتن مگر - Lean Concrete
  {
    lines: [
      { code: "080102", qty: 18.65 },
    ],
    baseTotal: 319884800,
    grandTotal: 432484249.6,
  },
  // ۵) جدول ریزمتره حجم بتن سازه‌ای - Structural Concrete
  // ایراد ۱: المان‌های پی با متریال «35 MPa» → ۰۸۰۱۰۸ جداگانه؛
  // بقیهٔ پی بدون متریال → ۰۸۰۱۰۵ (تنظیم ۲۰ MPa).
  {
    lines: [
      { code: "080105", qty: 18.65 },
      { code: "080105", qty: 7.18 },
      { code: "080106", qty: 4.68 },
      { code: "080107", qty: 250.36 },
      { code: "080108", qty: 152.83 },
    ],
    baseTotal: 9111404110,
    grandTotal: 12318618356.72,
  },
  // ۶) جدول ریزمتره سقف تیرچه بلوک - Joist Floor
  // اضافه‌بهای ۱۰۰۷۰۱ (مقاومت ۲۵ MPa، بند ۸ فصل دهم) روی کل مساحت سقف
  {
    lines: [
      { code: "100305", qty: 40.966508000000005 },
      { code: "100701", qty: 40.966508000000005 },
    ],
    baseTotal: 346187475.85400003,
    grandTotal: 468045467.35460806,
  },
  // ۷) جدول ریزمتره قالب‌بندی اسکلت - Superstructure Formwork
  // ایراد ۲: دال/تاوهٔ مستقل → ۰۶۰۴۰۱ (ارتفاع ۳٫۵ متر).
  {
    lines: [
      { code: "060301", qty: 668 },
      { code: "060401", qty: 11 },
      { code: "060501", qty: 1621 },
      { code: "060701", qty: 69 },
    ],
    baseTotal: 9535429000,
    grandTotal: 12891900008,
  },
  // ۸) جدول قالب‌بندی پی - Foundation Formwork
  {
    lines: [
      { code: "080105", qty: 152.9011044 },
      { code: "060101", qty: 167.3 },
    ],
    baseTotal: 3411530474.454,
    grandTotal: 4612389201.461808,
  },
  // ۹) جدول متره بتن پاشنه و یونولیت - Joist Concrete & EPS
  // مرحلهٔ ۱۱: پاشنهٔ تیرچه (۰٫۳۴ m³) حذف شد — بند ۳ فصل دهم؛
  // این جدول دیگر هیچ ردیف فهرست‌بها تولید نمی‌کند.
  {
    lines: [],
    baseTotal: 0,
    grandTotal: 0,
  },
];

function loadRealTables() {
  const dir = path.join(__dirname, "..", "..", "data", "export revit");
  return fs
    .readdirSync(dir)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(dir, f), "utf-8")));
}

describe("T08 engine parity: single-file computeProject vs Python", () => {
  it("exposes exactly 10 real export files", () => {
    expect(loadRealTables().length).toBe(10);
  });

  it.each(EXPECTED.map((e, i) => ({ e, i })))(
    "file #$i matches Python engine ($e.lines.length lines)",
    ({ e, i }) => {
      const tables = loadRealTables();
      const r = computeProject([tables[i]], OFFICIAL_1404_FEHREST, defaultSettings());

      // تعداد خطوط خروجی
      expect(r.lines.length).toBe(e.lines.length);

      // کدهای فهرست‌بها (به ترتیب خروجی engine)
      expect(r.lines.map((l) => l.code)).toEqual(e.lines.map((l) => l.code));

      for (let j = 0; j < e.lines.length; j++) {
        const want = e.lines[j];
        const got = r.lines[j];
        expect(got.code).toBe(want.code);
        expect(got.qty).toBeCloseTo(want.qty, 6);
        // مرحلهٔ ۱۱: ضریب پرت حذف شد؛ ضریب شاخص دورهٔ مبنا = ۱
        expect(got.indexFactor).toBeCloseTo(1, 6);
        expect(got.totalIndexed).toBeCloseTo(got.total, 2);
        // پایگاه رسمی: تطابق دقیق با اعتماد کامل
        expect(got.matchMethod).toBe("rule-exact");
        expect(got.confidence).toBeCloseTo(0.99, 6);
        expect(got.estimatedPrice).toBe(false);
      }

      // base_total و grand_total پروژه
      expect(r.baseTotal).toBeCloseTo(e.baseTotal, 4);
      expect(r.grandTotal).toBeCloseTo(e.grandTotal, 4);
    },
  );
});
