// T68 - اضافه‌بهای بتن مسلح (ردیف ۰۸۰۳۱۰ فهرست‌بهای ۱۴۰۴).
//
// شرط رسمی: «اضافه‌بها به ردیف‌های بتن‌ریزی، در صورت مصرف بتن در بتن مسلح»
// (۱۴۵٬۵۰۰ ریال/m³). مدرک «مسلح بودن»: جدول آرماتور پروژه ستون «Host
// Category» (دستهٔ المان میزبان) دارد که توسط پارسر نگه داشته می‌شود. گروه
// سازه‌ایِ میزبان (پی/ستون/تیر/سقف/پله/دیوار) با گروه رکوردهای تشکیل‌دهندهٔ
// هر خط بتن سازه‌ای تطبیق داده می‌شود؛ خط بتن مگر (lean) هرگز مسلح نیست.
// این ردیف **اختیاری** است و تنظیم بولین `surchargeReinforcedConcrete`
// (پیش‌فرض false) آن را فعال می‌کند.
import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { parseRevitFile, structuralGroup } from "../../src/lib/revitParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings, RevitTable } from "../../src/lib/types";

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

const REBAR_FILE = "جدول ریزمتره آرماتورها - Structural Rebar Schedule.txt";

describe("T68 — اضافه‌بهای بتن مسلح (۰۸۰۳۱۰)", () => {
  it("پارسر ستون «Host Category» جدول آرماتور را نگه می‌دارد", () => {
    const t = parseRevitFile(
      REBAR_FILE,
      fs.readFileSync(path.join(REVIT_DIR, REBAR_FILE), "utf-8"),
    ) as unknown as RevitTable;
    expect(t.kind).toBe("rebar_detailed");

    const cats = new Map<string, number>();
    let total = 0;
    for (const r of t.rows) {
      const c = (r.texts.hostCategory ?? "").trim();
      expect(c.length).toBeGreaterThan(0); // هر ردیف آرماتور واقعی دارای Host Category است
      cats.set(c, (cats.get(c) ?? 0) + (r.values.weight ?? 0));
      total += r.values.weight ?? 0;
    }

    // دسته‌های میزبان موجود در پروژهٔ نمونه
    expect([...cats.keys()].sort()).toEqual(
      [
        "Structural Column",
        "Structural Foundation",
        "Structural Framing",
        "Stairs",
        "Floor",
        "Wall",
        "<varies>",
      ].sort(),
    );
    // بیشترین وزن متعلق به پی است (۱۰٬۳۹۲٫۴ kg)
    expect(cats.get("Structural Foundation") ?? 0).toBeCloseTo(10392.4, 1);
    expect(total).toBeCloseTo(12103.46, 1);

    // پل نگاشت Host Category → گروه سازه‌ای (مبنای تشخیص بتن مسلح)
    expect(structuralGroup("Structural Framing", "structural_concrete")).toBe("تیر");
    expect(structuralGroup("Structural Column", "structural_concrete")).toBe("ستون");
    expect(structuralGroup("Structural Foundation", "structural_concrete")).toBe("پی");
    expect(structuralGroup("Floor", "structural_concrete")).toBe("سقف");
    expect(structuralGroup("Stairs", "structural_concrete")).toBe("پله");
    expect(structuralGroup("Wall", "structural_concrete")).toBe("دیوار");
    expect(structuralGroup("<varies>", "structural_concrete")).toBe("سایر"); // نامعلوم → مدرک نمی‌شود
  });

  it("پیش‌فرض: تنظیم خاموش است و ردیف ۰۸۰۳۱۰ وجود ندارد و totals مرجع است", () => {
    expect(defaultSettings().surchargeReinforcedConcrete).toBe(false);
    const r = pipeline(defaultSettings());
    expect(r.lines).toHaveLength(17);
    expect(r.lines.some((l: any) => l.code === "080310")).toBe(false);
    expect(r.baseTotal).toBeCloseTo(23218381337.01, 0);
    expect(r.grandTotal).toBeCloseTo(31391251567.64, 0);
  }, 30000);

  it("فعال‌سازی روی دادهٔ نمونه: متراکم‌ترین المان ۱۵۳٫۹۷ < ۱۸۰ → ردیفی نیست", () => {
    const off = pipeline(defaultSettings());
    const on = pipeline({ ...defaultSettings(), surchargeReinforcedConcrete: true });

    expect(on.lines).toHaveLength(off.lines.length);
    expect(on.lines).toHaveLength(17);
    expect(on.lines.some((l: any) => l.code === "080310")).toBe(false);
    expect(on.baseTotal).toBe(off.baseTotal);
    expect(on.grandTotal).toBe(off.grandTotal);
    expect(on.baseTotal).toBeCloseTo(23218381337.01, 0);
  }, 30000);

  it("قاعدهٔ per-element روی دادهٔ ساختگی: فقط المان با تراکم خودش > ۱۸۰", () => {
    // DENSE-01: ۲۰۰ kg / ۱٫۰ m³ = 200 > 180 → مشمول.
    // LIGHT-01: ۱۰۰ kg / ۱۰٫۰ m³ = 10 → مشمول نیست.
    // EDGE-01: ۳۶۰ kg / ۲٫۰ m³ = 180 → دقیقاً برابر آستانه، مشمول نیست.
    // JSL-TOP01-ST01: ۵۰۰ kg / ۱٫۰ m³ = 500 → رویهٔ تیرچه‌بلوک → مستثنی (بند ۳-۵).
    // دستهٔ «<varies>» → به هیچ المانی انتساب ندارد → مستثنی.
    const database = [
      { code: "080107", chapter: "08", desc: "بتن درجای ستون‌ها و تیرها",
        unit: "مترمکعب", price: 1000000, estimated: false },
      { code: "080310", chapter: "08",
        desc: "اضافه‌بها به ردیف‌های بتن‌ریزی، در صورت مصرف بتن در بتن مسلح",
        unit: "مترمکعب", price: 145500, estimated: false },
    ];
    const mkRow = (values: Record<string, number>, texts: Record<string, string>) =>
      ({ cells: [] as string[], values, texts, isSubtotal: false });
    const tables = [
      { id: "t1", fileName: "t.txt", title: "T", headers: [] as string[],
        kind: "structural_concrete", kindConfidence: 0.9, colMap: {}, warnings: [],
        grandTotal: {},
        rows: [
          mkRow({ volume: 1.0 }, { mark: "DENSE-01", category: "Structural Column", familyType: "Column", level: "L0" }),
          mkRow({ volume: 10.0 }, { mark: "LIGHT-01", category: "Structural Column", familyType: "Column", level: "L0" }),
          mkRow({ volume: 2.0 }, { mark: "EDGE-01", category: "Structural Column", familyType: "Column", level: "L0" }),
          mkRow({ volume: 1.0 }, { mark: "JSL-TOP01-ST01", category: "Floor", familyType: "Slab", level: "L0" }),
        ] },
      { id: "t2", fileName: "t.txt", title: "T", headers: [] as string[],
        kind: "rebar_detailed", kindConfidence: 0.9, colMap: {}, warnings: [],
        grandTotal: {},
        rows: [
          mkRow({ weight: 200.0 }, { hostMark: "DENSE-01" }),
          mkRow({ weight: 100.0 }, { hostMark: "LIGHT-01" }),
          mkRow({ weight: 360.0 }, { hostMark: "EDGE-01" }),
          mkRow({ weight: 500.0 }, { hostMark: "JSL-TOP01-ST01" }),
          mkRow({ weight: 999.0 }, { hostMark: "<varies>" }),
        ] },
    ];
    const s = { ...defaultSettings(), surchargeReinforcedConcrete: true };
    const res = computeProject(tables as never, database as never, s);

    const sc = res.lines.filter((l: any) => l.code === "080310");
    expect(sc).toHaveLength(1);
    const line = sc[0];
    expect(line.id).toBe("surcharge-080310");
    expect(line.unit).toBe("مترمکعب");
    expect(line.price).toBeCloseTo(145500, 0);
    // فقط DENSE-01 (۱٫۰ m³)؛ EDGE-01 دقیقاً ۱۸۰ است و مشمول نمی‌شود
    expect(line.qty).toBeCloseTo(1.0, 9);
    expect(line.total).toBeCloseTo(1.0 * 145500, 0);
    expect(line.matchMethod).toBe("rule-exact");
    expect(String(line.note)).toContain("DENSE-01");
    expect(String(line.note)).not.toContain("EDGE-01");
  }, 30000);
});
