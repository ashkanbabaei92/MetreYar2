// ─────────────────────────────────────────────────────────────
// T98 — فاز E-6 (بخش ۰): جدول کامل ΔP در ۶ ترکیب
//   گردکردن ضریب (بند ۸-۲) × completedWithinTerm (تبصرهٔ ۲ بند ۱-۸)
// (آینهٔ test_T98_e6_dp_table.py — خروجی‌ها باید bit-identical باشند).
//
// سناریوی مرجع §۱۴-۶: دورهٔ ۱۴۰۴/۰۱/۰۱ تا ۱۴۰۵/۰۲/۱۵،
// proposal_date = ۱۴۰۳/۱۲/۲۹، provisionalCoef1405q1 = 1.1530518586507572.
//
// جدول ΔP (مقادیر گردشدهٔ ۲ رقمی که در گزارش نمایش داده می‌شوند):
//   ┌──────────┬─────┬────────────────┬────────────────┬────────────────┬───────────────┐
//   │گردکردن   │ cwt │      ΔP        │    قطعی        │  علی‌الحساب     │   k_diff     │
//   ├──────────┼─────┼────────────────┼────────────────┼────────────────┼───────────────┤
//   │  خاموش   │ ─   │ ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴│ ۷٬۷۰۹٬۸۹۳٬۴۷۹٫۴۰│ ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴│      ۰        │
//   │  خاموش   │ بله │۱۰٬۴۶۰٬۴۲۹٬۳۴۴٫۸۸│ ۸٬۶۳۸٬۶۹۸٬۸۱۳٫۹۹│ ۱٬۸۲۱٬۷۳۰٬۵۳۰٫۸۹│ ۵۲۳٬۰۲۱٬۴۶۷٫۲۴│
//   │  خاموش   │ خیر │ ۹٬۹۳۷٬۴۰۷٬۸۷۷٫۶۴│ ۷٬۷۰۹٬۸۹۳٬۴۷۹٫۴۰│ ۲٬۲۲۷٬۵۱۴٬۳۹۸٫۲۴│      ۰        │
//   │  روشن    │ ─   │ ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲│ ۷٬۷۶۱٬۰۴۵٬۲۰۹٫۹۴│ ۲٬۲۲۳٬۲۳۲٬۱۹۸٫۲۸│      ۰        │
//   │  روشن    │ بله │۱۰٬۴۸۹٬۵۹۴٬۳۶۹٫۰۷│ ۸٬۶۳۹٬۱۷۸٬۲۷۸٫۹۱│ ۱٬۸۵۰٬۴۱۶٬۰۹۰٫۱۶│ ۵۰۵٬۳۱۶٬۹۶۰٫۸۶│
//   │  روشن    │ خیر │ ۹٬۹۸۴٬۲۷۷٬۴۰۸٫۲۲│ ۷٬۷۶۱٬۰۴۵٬۲۰۹٫۹۴│ ۲٬۲۲۳٬۲۳۲٬۱۹۸٫۲۸│      ۰        │
//   └──────────┴─────┴────────────────┴────────────────┴────────────────┴───────────────┘
//
// بندهای مسبب:
//   - گردکردن خاموش ≡ میراث پیش از E-6 (بند ۸-۲ اعمال نمی‌شود).
//   - cwt = بله ⇒ k = ۱ (تبصرهٔ ۲ بند ۱-۸)؛ k_diff = ΔP(k=1) − ΔP(k=0.95)
//     که طبق بند ۸-۴ به بخش قطعی افزوده می‌شود.
//   - cwt = ─ و cwt = خیر از نظر عددی یکسان هستند (k = ۰٫۹۵)؛
//     تفاوت فقط در برچسب قطعی/علی‌الحساب بودن k است (بند ۸-۳).
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import { splitRounded } from "../../src/lib/adjustment";
import type { ProjectSettings, ProjectResult, TadilResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");
const PROV_COEF = 1.1530518586507572;
const PROPOSAL_DATE = "۱۴۰۳/۱۲/۲۹";
const REF: Partial<ProjectSettings> = {
  baravordEnabled: true,
  workPeriodStart: "۱۴۰۴/۰۱/۰۱",
  workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
  provisionalCoef1405q1: PROV_COEF,
};

// مقادیر دقیق موتور (raw) — از اجرای مرجع پایتون (باید یکسان باشند)
const RAW: Record<string, [number, number, number, number]> = {
  "false|null": [9937407877.639488, 7709893479.404506, 2227514398.234982, 0.0],
  "false|true": [10460429344.88367, 8638698813.985767, 1821730530.897903, 523021467.244183],
  "false|false": [9937407877.639488, 7709893479.404506, 2227514398.234982, 0.0],
  "true|null": [9984277408.21705, 7761045209.936075, 2223232198.280975, 0.0],
  "true|true": [10489594369.074144, 8639178278.91072, 1850416090.163424, 505316960.857094],
  "true|false": [9984277408.21705, 7761045209.936075, 2223232198.280975, 0.0],
};
// مقادیر گردشدهٔ نمایشی (۲ رقم اعشار)
const SPLIT: Record<string, [number, number, number]> = {
  "false|null": [9937407877.64, 7709893479.4, 2227514398.24],
  "false|true": [10460429344.88, 8638698813.99, 1821730530.89],
  "false|false": [9937407877.64, 7709893479.4, 2227514398.24],
  "true|null": [9984277408.22, 7761045209.94, 2223232198.28],
  "true|true": [10489594369.07, 8639178278.91, 1850416090.16],
  "true|false": [9984277408.22, 7761045209.94, 2223232198.28],
};
// برآورد به‌هنگام (موتور ۲) — از k و گردکردن مستقل است
const BARAVORD = 45437742820.32315;

const COMBOS: [boolean, boolean | null][] = [
  [false, null], [false, true], [false, false],
  [true, null], [true, true], [true, false],
];

function toBuffer(p: string): ArrayBuffer {
  const b = fs.readFileSync(p);
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
}

function pipeline(settings: ProjectSettings): ProjectResult {
  const tables = fs
    .readdirSync(REVIT_DIR)
    .sort()
    .filter((f) => f.endsWith(".txt"))
    .map((f) => parseRevitFile(f, fs.readFileSync(path.join(REVIT_DIR, f), "utf-8")));
  const rows: unknown[] = [];
  for (const sub of fs.readdirSync(DYNAMO_DIR).sort()) {
    const sd = path.join(DYNAMO_DIR, sub);
    if (!fs.statSync(sd).isDirectory()) continue;
    for (const fn of fs.readdirSync(sd).sort()) {
      if (!fn.endsWith(".txt")) continue;
      (rows as unknown[]).push(...parseDynamoMapping(toBuffer(path.join(sd, fn)), fn).rows);
    }
  }
  return computeProject(tables, OFFICIAL_1404_FEHREST, settings, {
    rows,
    format: "v2",
    recordCount: rows.length,
    warnings: [],
  } as never);
}

function on(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return { ...defaultSettings(), tadilEnabled: true, proposalDate: PROPOSAL_DATE, ...extra };
}

const key = (rnd: boolean, cwt: boolean | null) =>
  `${rnd}|${cwt === null ? "null" : cwt}`;

// کش: هر ترکیب یک بار اجرا می‌شود
const tadilCache = new Map<string, TadilResult>();
const baravordCache = new Map<string, number>();

function tadilOf(rnd: boolean, cwt: boolean | null): TadilResult {
  const k = key(rnd, cwt);
  if (!tadilCache.has(k)) {
    const res = pipeline(on({ ...REF, coefRounding2080: rnd, completedWithinTerm: cwt }));
    tadilCache.set(k, res.adjustment.tadil!);
    baravordCache.set(k, res.adjustment.baravord?.result_amount ?? NaN);
  }
  return tadilCache.get(k)!;
}

function baravordOf(rnd: boolean, cwt: boolean | null): number {
  tadilOf(rnd, cwt);
  return baravordCache.get(key(rnd, cwt))!;
}

describe("T98 فاز E-6 (بخش ۰) — جدول ΔP در ۶ ترکیب", () => {
  it("هر ۶ ترکیب: مقادیر دقیق موتور مطابق جدول", () => {
    for (const [rnd, cwt] of COMBOS) {
      const t = tadilOf(rnd, cwt);
      const [dp, defi, prov, kdiff] = RAW[key(rnd, cwt)];
      expect(t.delta_p).toBeCloseTo(dp, 6);
      expect(t.delta_p_definitive).toBeCloseTo(defi, 6);
      expect(t.delta_p_provisional).toBeCloseTo(prov, 6);
      expect(t.k_diff).toBeCloseTo(kdiff, 6);
      expect(t.coef).toBeCloseTo(cwt === true ? 1.0 : 0.95, 9);
    }
  }, 600000);

  it("هر ۶ ترکیب: تفکیک گردشدهٔ نمایشی، قطعی + علی‌الحساب ≡ ΔP", () => {
    for (const [rnd, cwt] of COMBOS) {
      const t = tadilOf(rnd, cwt);
      const [r, a, b] = splitRounded(t.delta_p, t.delta_p_definitive, 2);
      expect(a + b).toBeCloseTo(r, 6);
      const [er, ea, eb] = SPLIT[key(rnd, cwt)];
      expect(r).toBeCloseTo(er, 5);
      expect(a).toBeCloseTo(ea, 5);
      expect(b).toBeCloseTo(eb, 5);
    }
  }, 600000);

  it("هر ۶ ترکیب: نامساوی کلیدی قطعی + علی‌الحساب ≡ ΔP (دقیق)", () => {
    for (const [rnd, cwt] of COMBOS) {
      const t = tadilOf(rnd, cwt);
      expect(t.delta_p_definitive + t.delta_p_provisional).toBeCloseTo(t.delta_p, 9);
    }
  }, 600000);

  it("گردکردن خاموش + cwt = ─ ≡ میراث پیش از E-6", () => {
    const t = tadilOf(false, null);
    expect(t.delta_p).toBeCloseTo(9937407877.639488, 9);
    const [r, a, b] = splitRounded(t.delta_p, t.delta_p_definitive, 2);
    expect(r).toBeCloseTo(9937407877.64, 6);
    expect(a).toBeCloseTo(7709893479.4, 6);
    expect(b).toBeCloseTo(2227514398.24, 6);
  }, 300000);

  it("cwt = ─ و cwt = خیر از نظر عددی یکسانند (بند ۸-۳ فقط برچسب را عوض می‌کند)", () => {
    for (const rnd of [false, true]) {
      const tn = tadilOf(rnd, null);
      const tf = tadilOf(rnd, false);
      for (const f of ["delta_p", "delta_p_definitive", "delta_p_provisional", "k_diff"] as const) {
        expect(tn[f]).toBeCloseTo(tf[f], 9);
      }
    }
  }, 600000);

  it("تبصرهٔ ۲ بند ۱-۸: k_diff = ΔP(k=1) − ΔP(k=0.95)", () => {
    for (const rnd of [false, true]) {
      const tt = tadilOf(rnd, true);
      const tf = tadilOf(rnd, false);
      expect(tt.k_diff).toBeCloseTo(tt.delta_p - tf.delta_p, 2);
      expect(tt.k_diff).toBeGreaterThan(0);
      expect(tf.k_diff).toBe(0);
    }
  }, 600000);

  it("موتور ۲ (برآورد به‌هنگام) از k و گردکردن مستقل است", () => {
    for (const [rnd, cwt] of COMBOS) {
      expect(baravordOf(rnd, cwt)).toBeCloseTo(BARAVORD, 6);
    }
  }, 600000);

  it("بند ۸-۲: اثر گردکردن روی ΔP کمتر از ۰٫۵٪ است", () => {
    for (const cwt of [null, true, false] as (boolean | null)[]) {
      const off = tadilOf(false, cwt);
      const onR = tadilOf(true, cwt);
      expect(Math.abs(onR.delta_p - off.delta_p) / off.delta_p).toBeLessThan(0.005);
    }
  }, 600000);
});
