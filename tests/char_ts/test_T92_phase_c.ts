// ─────────────────────────────────────────────────────────────
// T92 — فاز C: ایراد ۱۲ (آینهٔ test_T92_phase_c.py)
//
// سه تاریخ متمایز و هرگز ادغام‌نشدنی (ایراد ۱۲):
//   - «تاریخ شروع پیمان»            ← contractDate
//   - «تاریخ شروع دورهٔ صورت‌وضعیت»  ← periodStart
//   - «تاریخ پایان دورهٔ صورت‌وضعیت» ← periodEnd
// قاعده: شروع پیمان ≤ شروع دوره ≤ پایان دوره. در صورت نقض، خطا و
// جلوگیری از محاسبه/خروجی.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { exportWorkbook } from "../../src/lib/exporters";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { validateMeta } from "../../src/lib/adjustment";
import type { ProjectMeta } from "../../src/lib/types";

const BASE_META: ProjectMeta = {
  projectName: "T92",
  employer: "کارفرما",
  contractor: "پیمانکار",
  consultant: "مشاور",
  contractNo: "۱",
  location: "گرگان",
  reportNo: "۱",
  reportType: "دوره‌ای",
  periodStart: "۱۴۰۴/۰۱/۰۱",
  periodEnd: "۱۴۰۴/۰۳/۳۱",
  contractDate: "۱۴۰۳/۱۲/۲۹",
};

function errs(over: Partial<ProjectMeta> = {}): ReturnType<typeof validateMeta> {
  return validateMeta({ ...BASE_META, ...over });
}

// ── ترتیب معتبر ──

describe("T92 — ترتیب معتبر", () => {
  it("ترتیب درست بدون خطا", () => {
    expect(errs()).toEqual([]);
  });
  it("تاریخ‌های مساوی مجاز است", () => {
    expect(errs({ contractDate: "۱۴۰۴/۰۱/۰۱" })).toEqual([]);
    expect(errs({ contractDate: "۱۴۰۴/۰۱/۰۱", periodStart: "۱۴۰۴/۰۱/۰۱", periodEnd: "۱۴۰۴/۰۱/۰۱" })).toEqual([]);
  });
  it("تاریخ‌های خالی از بررسی معافند", () => {
    expect(errs({ contractDate: "", periodStart: "", periodEnd: "" })).toEqual([]);
    expect(errs({ contractDate: "", periodStart: "", periodEnd: "۱۴۰۴/۰۱/۰۱" })).toEqual([]);
  });
  it("ارقام فارسی و لاتین هر دو پذیرفته می‌شوند", () => {
    expect(errs({ contractDate: "1403/12/29" })).toEqual([]);
    expect(errs({ contractDate: "۱۴۰۳/۱۲/۲۹" })).toEqual([]);
  });
  it("meta خالی بدون خطا", () => {
    expect(validateMeta(null)).toEqual([]);
  });
});

// ── نقض ترتیب ──

describe("T92 — نقض ترتیب", () => {
  it("شروع پیمان بعد از شروع دوره", () => {
    const e = errs({ contractDate: "۱۴۰۴/۰۶/۰۱", periodEnd: "۱۴۰۴/۱۲/۲۹" });
    expect(e).toHaveLength(1);
    expect(e[0].level).toBe("خطا");
    expect(e[0].category).toBe("تاریخ‌ها");
    expect(e[0].message).toContain("شروع پیمان");
    expect(e[0].ref.startsWith("ایراد ۱۲")).toBe(true);
  });
  it("شروع دوره بعد از پایان دوره", () => {
    const e = errs({ periodStart: "۱۴۰۴/۰۶/۰۱", periodEnd: "۱۴۰۴/۰۳/۳۱" });
    expect(e).toHaveLength(1);
    expect(e[0].level).toBe("خطا");
    expect(e[0].message).toContain("شروع دوره");
  });
  it("شروع پیمان بعد از پایان دوره (دو خطا)", () => {
    const e = errs({ contractDate: "۱۴۰۴/۰۹/۰۱", periodEnd: "۱۴۰۴/۰۳/۳۱" });
    expect(e).toHaveLength(2);
    expect(e.every((x) => x.level === "خطا")).toBe(true);
    expect(e.some((x) => x.message.includes("شروع پیمان"))).toBe(true);
  });
  it("چند نقض همزمان", () => {
    const e = errs({ contractDate: "۱۴۰۵/۰۱/۰۱", periodStart: "۱۴۰۴/۰۶/۰۱", periodEnd: "۱۴۰۴/۰۳/۳۱" });
    expect(e).toHaveLength(3);
    expect(e.every((x) => x.level === "خطا")).toBe(true);
  });
});

// ── تاریخ نامعتبر ──

describe("T92 — تاریخ نامعتبر", () => {
  it("ماه نامعتبر", () => {
    const e = errs({ periodEnd: "۱۴۰۴/۱۳/۰۱" });
    expect(e).toHaveLength(1);
    expect(e[0].message).toContain("معتبر نیست");
    expect(e[0].item).toBe("تاریخ پایان دورهٔ صورت‌وضعیت");
  });
  it("تاریخ نامعتبر + نقض ترتیب", () => {
    const e = errs({ contractDate: "۱۴۰۴/۰۶/۰۱", periodStart: "bad" });
    expect(e).toHaveLength(2);
    expect(e.some((x) => x.message.includes("معتبر نیست"))).toBe(true);
    expect(e.some((x) => x.message.includes("شروع پیمان"))).toBe(true);
  });
});

// ── خروجی Excel ──

function exportSheets(meta: ProjectMeta): Record<string, unknown[][]> {
  const res = computeProject([], OFFICIAL_1404_FEHREST, defaultSettings());
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: XLSX.WorkBook) => {
    wb = value;
  });
  try {
    exportWorkbook(meta, res, defaultSettings(), []);
  } finally {
    mock.mockRestore();
  }
  const out: Record<string, unknown[][]> = {};
  for (const name of (wb as XLSX.WorkBook).SheetNames) {
    out[name] = XLSX.utils.sheet_to_json((wb as XLSX.WorkBook).Sheets[name], { header: 1 });
  }
  return out;
}

describe("T92 — خروجی Excel", () => {
  it("برچسب‌های جدید ایراد ۱۲ در هدر", () => {
    const sheets = exportSheets(BASE_META);
    const header = String(sheets["خلاصهٔ مالی و برآورد"]?.[2]?.[0] ?? "");
    expect(header).toContain("دورهٔ صورت‌وضعیت");
    expect(header).toContain("شروع پیمان");
    expect(header).not.toContain("شروع قرارداد");
  });
  it("بنر خطا روی خروجی با تاریخ‌های نامعتبر", () => {
    const sheets = exportSheets({ ...BASE_META, contractDate: "۱۴۰۵/۰۱/۰۱" });
    const banner = String(sheets["خلاصهٔ مالی و برآورد"]?.[5]?.[0] ?? "");
    expect(banner).toContain("خطا — تاریخ‌های پروژه نامعتبر است");
    expect(banner).toContain("پیش‌نویس");
  });
  it("بدون بنر خطا با تاریخ‌های معتبر", () => {
    const sheets = exportSheets(BASE_META);
    const banner = String(sheets["خلاصهٔ مالی و برآورد"]?.[5]?.[0] ?? "");
    expect(banner).not.toContain("خطا — تاریخ‌های پروژه نامعتبر است");
  });
});
