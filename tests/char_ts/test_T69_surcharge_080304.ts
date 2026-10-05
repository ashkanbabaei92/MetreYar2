// T69 - اضافه‌بهای ضخامت کم بتن (ردیف ۰۸۰۳۰۴ فهرست‌بهای ۱۴۰۴).
//
// شرط رسمی (فصل ۸ بند ۳-۳): «اضافه‌بها به ردیف‌های بتن‌ریزی، هرگاه ضخامت
// بتن برابر ۱۵ سانتی‌متر یا کمتر باشد» (۳۰۴٬۰۰۰ ریال/m³). این اضافه‌بها
// مختص **دال روی زمین** (بتن‌ریزی کف روی خاک) است و سقف‌های معلق شامل
// نمی‌شوند. ضخامت **فقط از داده‌های خود پروژه** استخراج می‌شود:
//   فقط ردیفی که در **جدول خودش** هم «حجم» و هم «مساحت» دارد ارزیابی
//   می‌شود → ضخامت = حجم ÷ مساحت. ردیف‌های فاقد مساحتِ هم‌جدولی (دال‌های
//   سقف، پله، تیر، ستون) هرگز ارزیابی نمی‌شوند؛ جفت‌سازی با مساحت
//   قالب‌بندی مجاز نیست چون کناره‌ها/پاها را شامل می‌شود و دیگر نشانگر
//   دال روی زمین نیست.
// این ردیف **اختیاری** است و تنظیم بولین `surchargeThinConcrete`
// (پیش‌فرض false) آن را فعال می‌کند. مقدار خالص است (بدون ضریب پرت —
// مرحلهٔ ۱۱ بخش ۱).
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile } from "../../src/lib/revitParser";
import {
  computeProject,
  defaultSettings,
  thinConcreteNet,
  THIN_CONCRETE_THRESHOLD_M,
} from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings, RevitTable, TableRow } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function loadAllMappingRows() {
  const rows: any[] = [];
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const subDir = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(subDir).isDirectory()) continue;
    for (const fn of fs.readdirSync(subDir).sort()) {
      if (!fn.endsWith(".txt")) continue;
      rows.push(...parseDynamoMapping(toBuffer(path.join(subDir, fn)), fn).rows);
    }
  }
  return rows;
}

function db() {
  return OFFICIAL_1404_FEHREST;
}

function pipeline(settings: ProjectSettings): any {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows = loadAllMappingRows();
  const mapping = { rows, format: "v2" as const, recordCount: rows.length, warnings: [] };
  return computeProject(tables as never, db(), settings, mapping as never);
}

function mkTable(kind: RevitTable["kind"], rows: [TableRow["values"], TableRow["texts"]][]): RevitTable {
  return {
    id: "t",
    fileName: "t.txt",
    title: "T",
    headers: [],
    kind,
    kindConfidence: 0.9,
    colMap: {},
    warnings: [],
    rows: rows.map(([values, texts]) => ({
      cells: [],
      values,
      texts,
      isSubtotal: false,
    })),
  } as unknown as RevitTable;
}

describe("T69 — اضافه‌بهای ضخامت کم بتن (۰۸۰۳۰۴)", () => {
  it("قاعدهٔ استخراج ضخامت روی دادهٔ ساختگی: هر چهار شاخص رفتار", () => {
    // ۱) بتن مگر (همان‌جدولی): ۱۰ m³ بر ۱۰۰ m² = ۱۰ cm ≤ ۱۵ → نازک.
    // ۲) پی (همان‌جدولی): ۲۰ m³ بر ۲۲٫۲ m² = ۹۰ cm > ۱۵ → نازک نیست.
// ۳) دال بدون مساحت در جدول خودش: ارزیابی نمی‌شود (جفت‌سازی با
//    قالب‌بندی مجاز نیست — فقط دال روی زمین).
    //    = ۵ cm) → نازک.
    // ۴) پله و تیر: حجم÷مساحت ضخامت نیست → هرگز ارزیابی نمی‌شوند.
    // ۵) دال ضخیم (۳ m³ بر ۱۰ m² = ۳۰ cm) → نازک نیست.
    const tables: RevitTable[] = [
      mkTable("lean_concrete", [
        [{ volume: 10, area: 100 }, { mark: "LC-01", familyType: "Lean Concrete - 100mm" }],
      ]),
      mkTable("structural_concrete", [
        [{ volume: 20, area: 22.2 }, { mark: "FT-1", familyType: "Wall Foundation: WF_A_1800x900" }],
        [{ volume: 2 }, { mark: "SL01", familyType: "Slab", category: "Floors" }],
        [{ volume: 3, area: 10 }, { mark: "SL02", familyType: "Slab", category: "Floors" }],
        [{ volume: 5 }, { mark: "STR01", familyType: "Stair", category: "Stairs" }],
        [{ volume: 3 }, { mark: "B01", familyType: "Beam", category: "Structural Framing" }],
      ]),
      mkTable("formwork_super", [
        [{ area: 40 }, { mark: "SL01", category: "Floors" }],
        [{ area: 50 }, { mark: "STR01", category: "Stairs" }],
        [{ area: 100 }, { mark: "B01", category: "Structural Framing" }],
      ]),
    ];
    expect(thinConcreteNet(tables)).toBeCloseTo(10.0, 9);
    expect(THIN_CONCRETE_THRESHOLD_M).toBe(0.15);
  });

  it("دادهٔ واقعی: فقط بتن مگر (۹٫۹۷ cm) = ۱۸٫۶۵ m³ نازک", () => {
    const tables = fs
      .readdirSync(REVIT_DIR)
      .sort()
      .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
    expect(thinConcreteNet(tables as never)).toBeCloseTo(18.65, 3);
  });

  it("پیش‌فرض: تنظیم خاموش است و ردیف ۰۸۰۳۰۴ وجود ندارد و totals مرجع است", () => {
    expect(defaultSettings().surchargeThinConcrete).toBe(false);
    const r = pipeline(defaultSettings());
    expect(r.lines).toHaveLength(17);
    expect(r.lines.some((l: any) => l.code === "080304")).toBe(false);
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 0);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 0);
  }, 30000);

  it("فعال‌سازی روی دادهٔ نمونه: ۱۸٫۶۵ m³ نازک × ۳۰۴٬۰۰۰ ریال = ۵٬۶۶۹٬۶۰۰ ریال", () => {
    const off = pipeline(defaultSettings());
    const on = pipeline({ ...defaultSettings(), surchargeThinConcrete: true });

    expect(on.lines).toHaveLength(18);
    const sc = on.lines.filter((l: any) => l.code === "080304");
    expect(sc).toHaveLength(1);
    const line = sc[0];
    expect(line.id).toBe("surcharge-080304");
    expect(line.unit).toBe("مترمکعب");
    expect(line.price).toBeCloseTo(304000, 0);
    expect(line.qty).toBeCloseTo(18.65, 3);
    expect(line.total).toBeCloseTo(18.65 * 304000, 0);
    expect(line.matchMethod).toBe("rule-exact");

    expect(on.baseTotal).toBeCloseTo(off.baseTotal + line.total, 0);
    expect(on.baseTotal).toBeCloseTo(23218381337.01 + 18.65 * 304000, 0);
  }, 30000);
});
