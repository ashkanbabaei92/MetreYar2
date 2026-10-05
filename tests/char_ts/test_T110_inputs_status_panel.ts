// ─────────────────────────────────────────────────────────────
// T110 — فاز E-6 Part C گام ۱۲ (حرف g): پنلِ «وضعیت ورودی‌ها»
//
// تک‌منبعِ حقیقتِ تفسیرهای «منتظر تأیید کاربر»: PENDING_INTERPRETATIONS
// در src/lib/adjustment.ts — استفاده در پنلِ React و شیتِ Excel
// «مقادیر منتظر تأیید». این تست بررسی می‌کند:
//   ۱) ساختار: هر ورودی {no, subject, implemented, alternative, effect}.
//   ۲) شماره‌ها ۱..N پشتِ سرِ هم و یکتا هستند.
//   ۳) هیچ فیلدی خالی نیست (قاعدهٔ طلایی: هر ورودی مستند است).
//   ۴) شیتِ Excel «مقادیر منتظر تأیید» شاملِ جدول می‌شود.
//   ۵) موضوع‌های کلیدی با نسخهٔ Python (PENDING_INTERPRETATIONS در app.py)
//      یکی هستند (پاریتی).
// آینهٔ tests/char_python/test_T110_inputs_status_panel.py
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "fs";
import * as path from "path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import * as XLSX from "xlsx";
import { exportWorkbook } from "../../src/lib/exporters";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { parseFehrestText, mergeFehrest } from "../../src/data/fehrest";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { PENDING_INTERPRETATIONS } from "../../src/lib/adjustment";
import type { ProjectSettings } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");

// subjectهای MUST — باید در هر دو زبان یکسان باشند (پاریتی)
const MUST_SUBJECTS = [
  "ضریب k ورودی کاربر نیست (بند ۱-۸)",
  "مبنای کسرِ ۵٪ (بند ۷)",
  "گردنشدنِ ضریبِ تبدیلِ ۳-۵ قبل از ضرب در مبلغ",
  "مبنای «مبلغ برآورد» در سقفِ ۱۰٪ نامه-۶ (گام ۷)",
];

describe("T110 — پنلِ وضعیت ورودی‌ها (گام ۱۲)", () => {
  // ── ۱) ساختار و یکتاییِ شماره‌ها ──
  it("structure is well-formed five-field entries", () => {
    expect(PENDING_INTERPRETATIONS.length).toBeGreaterThanOrEqual(18);
    for (const e of PENDING_INTERPRETATIONS) {
      expect(typeof e.no).toBe("number");
      expect(e.no).toBeGreaterThan(0);
      for (const txt of [e.subject, e.implemented, e.alternative, e.effect]) {
        expect(typeof txt).toBe("string");
        expect(txt.trim().length).toBeGreaterThan(0);
      }
    }
  });

  it("numbers are contiguous and unique", () => {
    const nos = PENDING_INTERPRETATIONS.map((e) => e.no);
    expect(nos).toEqual(
      Array.from({ length: PENDING_INTERPRETATIONS.length }, (_, i) => i + 1),
    );
    expect(new Set(nos).size).toBe(nos.length);
  });

  // ── ۲) موضوع‌های کلیدی موجودند (پاریتیِ Must با Python) ──
  it("key subjects present", () => {
    const subjects = PENDING_INTERPRETATIONS.map((e) => e.subject);
    for (const s of MUST_SUBJECTS) {
      expect(subjects).toContain(s);
    }
  });

  // ─ـ ۳) تفسیرِ سقفِ ۱۰٪ (تفسیر ۱۸) اثرِ عددیِ مستند دارد ──
  it("ceiling entry has numeric effect", () => {
    const ceil = PENDING_INTERPRETATIONS.filter((e) => e.no === 18);
    expect(ceil).toHaveLength(1);
    const e = ceil[0];
    expect(e.implemented).toContain("base_total");
    expect(e.alternative).toContain("grand_total");
    expect(e.effect).toContain("۲٫۵ میلیارد");
  });

  // ── ۴) شیتِ Excel «مقادیر منتظر تأیید» جدول را در بر دارد ──
  it("excel sheet contains interpretations", () => {
    const s: ProjectSettings = {
      ...defaultSettings(),
      tadilEnabled: true,
      proposalDate: "۱۴۰۳/۱۲/۲۹",
      workPeriodStart: "۱۴۰۴/۰۱/۰۱",
      workPeriodEnd: "۱۴۰۴/۱۲/۲۹",
    };
    const revitDir = path.join(ROOT, "data", "export revit");
    const tables = fs.readdirSync(revitDir).sort().map((f) =>
      parseRevitFile(f, fs.readFileSync(path.join(revitDir, f), "utf-8")));
    const rows: any[] = [];
    const dynamoDir = path.join(ROOT, "data", "dynamo");
    for (const sub of fs.readdirSync(dynamoDir).sort()) {
      const subDir = path.join(dynamoDir, sub);
      if (!fs.statSync(subDir).isDirectory()) continue;
      for (const fn of fs.readdirSync(subDir).sort()) {
        if (!fn.endsWith(".txt")) continue;
        const b = fs.readFileSync(path.join(subDir, fn));
        rows.push(...parseDynamoMapping(
          b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as never,
          fn).rows);
      }
    }
    const mapping = { rows, format: "v2" as const, recordCount: rows.length,
                      warnings: [] };
    const fehrestFile = path.join(ROOT, "data", "fehrest baha 1404",
                                  "all 1404 fehrest.txt");
    const db = mergeFehrest(OFFICIAL_1404_FEHREST,
                            parseFehrestText(fs.readFileSync(fehrestFile, "utf-8")));
    const result = computeProject(tables as never, db, s, mapping as never);

    let wb: any;
    const mock = vi.spyOn(XLSX, "writeFile").mockImplementation((v: any) => {
      wb = v;
    });
    try {
      exportWorkbook({ projectName: "T110", reportNo: "1" } as any, result, s,
                     []);
    } finally {
      mock.mockRestore();
    }
    expect(wb.SheetNames).toContain("مقادیر منتظر تأیید");
    const rows2 = XLSX.utils.sheet_to_json<any[]>(
      wb.Sheets["مقادیر منتظر تأیید"], { header: 1 });
    const joined = rows2.map((r) => r.join(" ")).join("\n");
    expect(joined).toContain("تفسیرهای ابهامِ بخشنامه — منتظر تأیید کاربر");
    for (const e of PENDING_INTERPRETATIONS) {
      expect(joined).toContain(e.subject);
    }
  });
});
