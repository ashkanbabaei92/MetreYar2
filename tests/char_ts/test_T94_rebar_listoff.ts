// T94 - لیستوفر آرماتور (ایراد ۱۱) — آینهٔ tests/char_python/test_T94_rebar_listoff.py
//
// ستون‌های رسمی: مارک | گروه سازه‌ای | طبقه | قطر | تعداد | طول هر شاخه |
// طول کل | وزن واحد | وزن کل | شکل خم. قواعد صریح ایراد ۱۱:
//   - مارک هرگز «—» نیست؛ در نبود پارامتر «Rebar Number/Mark» → «بدون مارک»
//     + هشدار.
//   - گروه هرگز «سایر» نیست؛ در نبود «Host Category» قابل‌تشخیص → «نامشخص»
//     + هشدار.
//   - جمع‌ها به تفکیک قطر و گروه سازه‌ای.
import { describe, it, expect, vi } from "vitest";
import type { RevitTable, ProjectResult } from "../../src/lib/types";
import { extractRebar, defaultSettings } from "../../src/lib/engine";
import { rebarListGroup, rebarListMark } from "../../src/lib/revitParser";

vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { exportWorkbook } from "../../src/lib/exporters";

function table(): RevitTable {
  return {
    id: "T94-rebar",
    fileName: "T94.txt",
    title: "T94 Rebar Schedule",
    headers: [],
    kind: "rebar_detailed",
    kindConfidence: 1,
    colMap: {},
    warnings: [],
    grandTotal: {},
    rows: [
      // ۱ — میزبان «Structural Foundation» → گروه پی
      {
        cells: [],
        values: { weight: 60.5, diameter: 14, count: 5, length: 50 },
        texts: {
          mark: "FT-01", barType: "AIII", material: "AIII",
          hostCategory: "Structural Foundation", level: "Story1", shape: "L",
        },
        isSubtotal: false,
      },
      // ۲ — میزبان «<varies>» → گروه از مارک (تیر)
      {
        cells: [],
        values: { weight: 98.6, diameter: 20, count: 2, length: 40 },
        texts: {
          mark: "B01-ST01-MAIN-T", barType: "AIII", material: "AIII",
          hostCategory: "<varies>", level: "Story2",
        },
        isSubtotal: false,
      },
      // ۳ — هیچ مارکی وجود ندارد → «بدون مارک» + گروه نامشخص
      {
        cells: [],
        values: { weight: 1.18, diameter: 8, count: 1, length: 3 },
        texts: { barType: "AIII", material: "AIII" },
        isSubtotal: false,
      },
      // ۴ — مارک غیرقابل‌تشخیص و بدون میزبان → گروه نامشخص
      {
        cells: [],
        values: { weight: 4.44, diameter: 10, count: 4, length: 16 },
        texts: { mark: "ZZ-99", barType: "AIII", material: "AIII" },
        isSubtotal: false,
      },
      // ۵ — میزبان «Floor» → دال (واژگان لیستوفر)
      {
        cells: [],
        values: { weight: 22.2, diameter: 12, count: 3, length: 33 },
        texts: { mark: "SL-N1", barType: "AIII", material: "AIII", hostCategory: "Floor" },
        isSubtotal: false,
      },
    ],
  };
}

function extract() {
  return extractRebar([table()]);
}

describe("T94 — helpers مستقیم", () => {
  it("rebarListMark هرگز «—» برنمی‌گرداند", () => {
    expect(rebarListMark("FT-01")).toBe("FT-01");
    expect(rebarListMark("", "  ", undefined as never)).toBe("بدون مارک");
    expect(rebarListMark("  spaced  ")).toBe("spaced");
    expect(rebarListMark("A", "B")).toBe("A");
    expect(rebarListMark("", "B")).toBe("B");
  });

  it("rebarListGroup هرگز «سایر» برنمی‌گرداند", () => {
    // میزبان برنده است
    expect(rebarListGroup("Structural Foundation", "هرچیزی", "rebar_detailed"))
      .toEqual(["پی", false]);
    // «<varies>» نادیده گرفته می‌شود → سقوط به مارک
    expect(rebarListGroup("<varies>", "B01-ST01-MAIN", "rebar_detailed"))
      .toEqual(["تیر", false]);
    // واژگان: Floor میزبان → «سقف» → «دال»
    expect(rebarListGroup("Floor", "X", "rebar_detailed")[0]).toBe("دال");
    // غیرقابل‌تشخیص → «نامشخص» + پرچم هشدار
    expect(rebarListGroup("", "ZZ-99", "rebar_detailed")).toEqual(["نامشخص", true]);
    // «سقف تیرچه» حفظ می‌شود (به «دال» تبدیل نمی‌شود)
    const g = rebarListGroup("Structural Framing Joist", "JST-1", "rebar_joist")[0];
    expect(["سقف تیرچه", "تیر"]).toContain(g);
  });
});

describe("T94 — استخراج لیستوفر", () => {
  it("ستون‌ها و قواعد ایراد ۱۱", () => {
    const { lines } = extract();
    expect(lines).toHaveLength(5);
    for (const r of lines) {
      expect(r.mark).not.toBe("—");
      expect(r.group).not.toBe("سایر");
      expect(typeof r.level).toBe("string");
      // طول هر شاخه = طول کل / تعداد
      expect(r.perBarLength).toBeCloseTo(r.totalLength / r.count, 9);
      // وزن واحد = وزن / طول کل
      if (r.totalLength) expect(r.unitWeight).toBeCloseTo(r.weight / r.totalLength, 9);
      else expect(r.unitWeight).toBe(0);
    }
  });

  it("گروه و طبقه از میزبان/مارک", () => {
    const { lines } = extract();
    const byMark = new Map(lines.map((r) => [r.mark, r]));
    expect(byMark.get("FT-01")?.group).toBe("پی"); // از Host Category
    expect(byMark.get("FT-01")?.level).toBe("Story1");
    expect(byMark.get("B01-ST01-MAIN-T")?.group).toBe("تیر"); // <varies> → مارک
    expect(byMark.get("B01-ST01-MAIN-T")?.level).toBe("Story2");
    expect(byMark.get("SL-N1")?.group).toBe("دال"); // Floor → دال
    expect(byMark.get("ZZ-99")?.group).toBe("نامشخص");
    expect(byMark.get("ZZ-99")?.level).toBe("");
    const noMark = lines.filter((r) => r.mark === "بدون مارک");
    expect(noMark).toHaveLength(1);
    expect(noMark[0].group).toBe("نامشخص");
    expect(noMark[0].perBarLength).toBeCloseTo(3.0, 9);
  });

  it("هشدارها یکی به ازای هر جدول (نه هر ردیف)", () => {
    const { warnings } = extract();
    expect(warnings).toHaveLength(2);
    expect(warnings.some((w) => w.includes("«بدون مارک»"))).toBe(true);
    expect(warnings.some((w) => w.includes("«نامشخص»"))).toBe(true);
    const nm = warnings.find((w) => w.includes("«بدون مارک»"))!;
    expect(nm).toContain("۱ ردیف");
    const ug = warnings.find((w) => w.includes("«نامشخص»"))!;
    expect(ug).toContain("۲ ردیف");
  });
});

describe("T94 — خروجی Excel", () => {
  function sheetRows(): (string | number)[][] {
    const { lines } = extract();
    const result = {
      lines: [], rebar: lines, chapterSums: [], baseTotal: 0, floorsAmount: 0,
      overheadAmount: 0, regionalAmount: 0, siteSetup: 0, grossPayable: 0,
      grandTotal: 0, insurance: 0, tax: 0, goodJob: 0, advancePayment: 0,
      totalDeductions: 0, netPayable: 0, index: null,
      quality: {
        tablesParsed: 0, tablesUnknown: 0, mappingRecords: 0, rowsRead: 0,
        linesMatched: 0, linesExact: 0, linesFuzzy: 0, linesEstimated: 0,
        linesReview: 0, warnings: [] as string[],
      },
    } as unknown as ProjectResult;
    let wb: any;
    const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((value: any) => {
      wb = value;
    });
    try {
      exportWorkbook(
        { projectName: "T94", reportNo: "1" } as any,
        result,
        defaultSettings(),
        [],
      );
    } finally {
      mock.mockRestore();
    }
    const ws = wb.Sheets["لیستوفر آرماتور"];
    expect(ws, "rebar sheet missing").toBeDefined();
    return XLSX.utils.sheet_to_json(ws, { header: 1, blankrows: true }) as any;
  }

  it("سرستون ۱۰‌تایی و قواعد سلول‌ها", () => {
    const rows = sheetRows();
    const hdrI = rows.findIndex(
      (r) => r[0] === "مارک" && r.slice(1, 3).includes("گروه سازه‌ای"),
    );
    expect(hdrI).toBeGreaterThanOrEqual(0);
    expect(rows[hdrI].slice(0, 10)).toEqual([
      "مارک", "گروه سازه‌ای", "طبقه", "قطر (mm)", "تعداد",
      "طول هر شاخه (m)", "طول کل (m)", "وزن واحد (kg/m)", "وزن کل (kg)", "شکل خم",
    ]);
    const data = rows
      .slice(hdrI + 1)
      .filter((r) => r[0] && !String(r[0]).startsWith("جمع"));
    expect(data).toHaveLength(5);
    for (const r of data) {
      expect(r[0]).not.toBe("—");
      expect(r[1]).not.toBe("سایر");
    }
  });

  it("جمع به تفکیک قطر/گروه برابر جمع کل", () => {
    const rows = sheetRows();
    const labels = rows.map((r) => r[0]);
    expect(labels).toContain("جمع به تفکیک قطر");
    expect(labels).toContain("جمع به تفکیک گروه");
    expect(labels).toContain("جمع کل");

    const { lines } = extract();
    const totalW = lines.reduce((a, r) => a + r.weight, 0);
    const totRow = rows.find((r) => r[0] === "جمع کل");
    expect(Number(totRow?.[8])).toBeCloseTo(totalW, 6);

    function sectionSum(start: string, end: string): number {
      const i0 = rows.findIndex((r) => r[0] === start);
      if (i0 < 0) return 0;
      let s = 0;
      for (const r of rows.slice(i0 + 1)) {
        if (r[0] === end) break;
        if (r[8] !== undefined && r[8] !== "") s += Number(r[8]);
      }
      return s;
    }

    expect(sectionSum("جمع به تفکیک قطر", "جمع به تفکیک گروه")).toBeCloseTo(totalW, 6);
    expect(sectionSum("جمع به تفکیک گروه", "جمع کل")).toBeCloseTo(totalW, 6);
  });
});
