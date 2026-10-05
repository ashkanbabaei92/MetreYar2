// ─────────────────────────────────────────────────────────────
// T93 — فاز C: ایراد ۱۳ (آینهٔ test_T93_jalali.py)
//
// - تبدیل شمسی ↔ میلادی (دو طرفه) — جستجوی دودویی روی g2j.
// - jalaliToISO: متن شمسی → ISO میلادی (ستون مخفی Excel).
// - شیت «سوابق صورت وضعیت»: متن شمسی + ستون مخفی میلادی واقعی.
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
import { g2j, jalaliToGregorian, todayJalali } from "../../src/lib/farsi";
import { jalaliToISO } from "../../src/lib/adjustment";
import type { ProjectMeta, StatusReportRecord } from "../../src/lib/types";

const BASE_META: ProjectMeta = {
  projectName: "T93", employer: "کارفرما", contractor: "پیمانکار", consultant: "مشاور",
  contractNo: "۱", location: "گرگان", reportNo: "۱", reportType: "دوره‌ای",
  periodStart: "۱۴۰۴/۰۱/۰۱", periodEnd: "۱۴۰۴/۰۳/۳۱", contractDate: "۱۴۰۳/۱۲/۲۹",
};

// ── تبدیل دوطرفه ──

describe("T93 — تبدیل شمسی↔میلادی", () => {
  it.each([
    [2025, 3, 21], [2024, 3, 20], [2023, 3, 21],
    [2025, 6, 21], [2026, 1, 1], [2025, 12, 31],
  ])("گردش میلادی→شمسی→میلادی %i-%i-%i", (gy, gm, gd) => {
    const j = g2j(gy, gm, gd);
    const back = jalaliToGregorian(...j);
    expect(back).toEqual([gy, gm, gd]);
  });

  it.each([
    [1404, 1, 1], [1403, 1, 1], [1402, 1, 1],
    [1404, 7, 1], [1404, 12, 29], [1403, 12, 30],
    [1405, 1, 1], [1405, 7, 8],
  ])("گردش شمسی→میلادی→شمسی %i/%i/%i", (jy, jm, jd) => {
    const g = jalaliToGregorian(jy, jm, jd);
    expect(g).not.toBeNull();
    expect(g2j(...(g as [number, number, number]))).toEqual([jy, jm, jd]);
  });

  it("نوروز ۱۴۰۴ = ۲۱ مارس ۲۰۲۵ (مرجع تقویم رسمی)", () => {
    expect(jalaliToGregorian(1404, 1, 1)).toEqual([2025, 3, 21]);
    expect(g2j(2025, 3, 21)).toEqual([1404, 1, 1]);
  });

  it("۱۴۰۳ کبیسه است، ۱۴۰۴ نیست", () => {
    expect(jalaliToGregorian(1403, 12, 30)).toEqual([2025, 3, 20]);
    // ۱۴۰۴ اسفند ۳۰ ندارد → null (نه پیش‌فرض، نه حدس)
    expect(jalaliToGregorian(1404, 12, 30)).toBeNull();
  });

  it.each([[1404, 13, 1], [1404, 0, 1], [1404, 12, 32], [1299, 1, 1]])(
    "تاریخ شمسی نامعتبر → null: %i/%i/%i",
    (jy, jm, jd) => {
      expect(jalaliToGregorian(jy, jm, jd)).toBeNull();
    },
  );
});

// ── jalaliToISO ──

describe("T93 — jalaliToISO", () => {
  it("نگاشت درست (ارقام فارسی و لاتین)", () => {
    expect(jalaliToISO("۱۴۰۴/۰۱/۰۱")).toBe("2025-03-21");
    expect(jalaliToISO("1404/01/01")).toBe("2025-03-21");
    expect(jalaliToISO("۱۴۰۳/۱۲/۳۰")).toBe("2025-03-20");
    expect(jalaliToISO("۱۴۰۴/۰۳/۳۱")).toBe("2025-06-21"); // خرداد ۳۱
  });
  it("ورودی نامعتبر → null", () => {
    expect(jalaliToISO("")).toBeNull();
    expect(jalaliToISO("نامعتبر")).toBeNull();
    expect(jalaliToISO("1404/13/01")).toBeNull();
    expect(jalaliToISO(null)).toBeNull();
  });
  it("todayJalali قابل تجزیه است", () => {
    // امروز شمسی معتبر → ISO معتبر
    const iso = jalaliToISO(todayJalali());
    expect(iso).not.toBeNull();
    expect(iso).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

// ── شیت Excel: ستون مخفی میلادی ──

function exportWb(history: StatusReportRecord[]): XLSX.WorkBook {
  const res = computeProject([], OFFICIAL_1404_FEHREST, defaultSettings());
  let wb: XLSX.WorkBook | undefined;
  const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((v: XLSX.WorkBook) => {
    wb = v;
  });
  try {
    exportWorkbook(BASE_META, res, defaultSettings(), history);
  } finally {
    mock.mockRestore();
  }
  return wb as XLSX.WorkBook;
}

describe("T93 — شیت Excel «سوابق صورت وضعیت»", () => {
  it("ستون‌های میلادی مخفی + مقادیر تاریخ واقعی", () => {
    const wb = exportWb([{
      id: "1", createdAt: "2025-06-21T00:00:00.000Z",
      reportNo: "۱", reportType: "موقت",
      periodStart: "۱۴۰۴/۰۱/۰۱", periodEnd: "۱۴۰۴/۰۳/۳۱",
      grossPayable: 1e9, totalDeductions: 1e8, netPayable: 9e8, currentWork: 9e8,
    }]);
    const ws = wb.Sheets["سوابق صورت وضعیت"];
    expect(ws).toBeTruthy();
    // هدر ستون‌های میلادی
    const rows = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1 });
    const headerRow = rows[5] as unknown[];
    expect(headerRow[8]).toBe("دوره از (میلادی)");
    expect(headerRow[9]).toBe("دوره تا (میلادی)");
    // متن شمسی در ستون‌های C/D
    const dataRow = rows[6] as unknown[];
    expect(dataRow[2]).toBe("۱۴۰۴/۰۱/۰۱");
    expect(dataRow[3]).toBe("۱۴۰۴/۰۳/۳۱");
    // ستون‌های I/J مخفی‌اند
    const cols = (ws as any)["!cols"] as { hidden?: boolean }[];
    expect(cols[8].hidden).toBe(true);
    expect(cols[9].hidden).toBe(true);
    // مقادیر میلادی واقعی (تبدیل تاریخ SheetJS)
    const iCell = ws["I7"] as { v?: number; z?: string };
    const jCell = ws["J7"] as { v?: number; z?: string };
    expect(iCell).toBeTruthy();
    expect(jCell).toBeTruthy();
    // serial تاریخ ۲۰۲۵-۰۳-۲۱
    const base = Date.UTC(1899, 11, 30);
    const expI = Math.round((Date.UTC(2025, 2, 21) - base) / 86400000);
    const expJ = Math.round((Date.UTC(2025, 5, 21) - base) / 86400000);
    expect(iCell.v).toBeCloseTo(expI, 0);
    expect(jCell.v).toBeCloseTo(expJ, 0);
  });

  it("تاریخ‌های خالی → سلول خالی، ولی هدر ستون‌ها موجود", () => {
    const wb = exportWb([{
      id: "1", createdAt: "2025-01-01T00:00:00.000Z",
      reportNo: "۱", reportType: "موقت",
      periodStart: "", periodEnd: "",
      grossPayable: 0, totalDeductions: 0, netPayable: 0, currentWork: 0,
    }]);
    const ws = wb.Sheets["سوابق صورت وضعیت"];
    const rows = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1 });
    const headerRow = rows[5] as unknown[];
    expect(headerRow[8]).toBe("دوره از (میلادی)");
    const iCell = ws["I7"];
    expect(iCell == null || iCell.v === "").toBe(true);
  });
});
