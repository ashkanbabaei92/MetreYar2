// ─────────────────────────────────────────────────────────────
// T117 — پاریتیِ اثرِ واقعیِ تصمیمات (فاز E-9 §۱)
// (آینهٔ test_T117_decision_impact.py)
//
// اثرِ هر تصمیمِ باز با اجرای واقعیِ موتور روی پروژهٔ مرجع اندازه گرفته و
// قفل می‌شود. منبعِ اعداد: tools/decision_impact.py →
// docs/decision_impact.csv. نکته: D-03 و D-13 صفر **نیستند**.
// ─────────────────────────────────────────────────────────────
import { describe, expect, it, vi } from "vitest";
import * as fs from "node:fs";
import * as path from "node:path";
vi.mock("xlsx", async () => {
  const actual = await vi.importActual("xlsx");
  return { ...actual, writeFile: vi.fn() };
});
import { parseRevitFile } from "../../src/lib/revitParser";
import { parseDynamoMapping } from "../../src/lib/mappingParser";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { OFFICIAL_1404_FEHREST } from "../../src/data/officialFehrest";
import type { ProjectSettings, ProjectResult } from "../../src/lib/types";

const ROOT = path.join(__dirname, "..", "..");
const REVIT_DIR = path.join(ROOT, "data", "export revit");
const DYNAMO_DIR = path.join(ROOT, "data", "dynamo");

const PROV_COEF = 1.1530518586507572;

function baseSettings(extra: Partial<ProjectSettings> = {}): ProjectSettings {
  return {
    ...defaultSettings(),
    tadilEnabled: true,
    tadilApproved: true,
    proposalDate: "۱۴۰۳/۱۲/۲۹",
    baravordEnabled: true,
    baravordApproved: true,
    workPeriodStart: "۱۴۰۴/۰۱/۰۱",
    workPeriodEnd: "۱۴۰۵/۰۲/۱۵",
    provisionalCoef1405q1: PROV_COEF,
    ...extra,
  };
}

const NEW1E9: Partial<ProjectSettings> = {
  newItemAmount: 1e9,
  newItemBasePeriod: "1404Q1",
};

type Scenario = {
  id: string;
  flip: Partial<ProjectSettings>;
  baseFlip?: Partial<ProjectSettings>;
  expDp: number;
  expBar: number;
};

const SCENARIOS: Scenario[] = [
  { id: "D-01", flip: { completedWithinTerm: true },
    expDp: 10489594369.074144, expBar: 45437742820.323151 },
  { id: "D-03", flip: { coefRounding2080: false },
    expDp: 9937407877.639488, expBar: 45437742820.323151 },
  { id: "D-04", flip: { negativeCoefRounding: "toward_zero" },
    expDp: 9984277408.217051, expBar: 45437742820.323151 },
  { id: "D-08", flip: { faultDeductionOnNegative: true },
    expDp: 9984277408.217051, expBar: 45437742820.323151 },
  { id: "D-09", flip: { provisionalDiffMethod: "own_period" },
    expDp: 9984277408.217051, expBar: 45437742820.323151 },
  { id: "D-10",
    flip: { contractExtensions: [
      { date: "۱۴۰۵/۰۲/۱۵", months: 3, kind: "مجاز",
        docNo: "سناریوی ابزار" } ] },
    expDp: 9984277408.217051, expBar: 45437742820.323151 },
  { id: "D-11", flip: { indexMethod: "رشته‌ای" },
    expDp: 9725954520.896103, expBar: 46172170291.967438 },
  { id: "D-13", flip: { indexMethod: "رشته‌ای" },
    expDp: 9725954520.896103, expBar: 46172170291.967438 },
  { id: "D-14", flip: { ...NEW1E9, newItemMethod: "فهرست پیمان" },
    expDp: 10294107505.304430, expBar: 46908603903.783905 },
  { id: "D-15",
    flip: { ...NEW1E9, newItemMethod: "قیمت روز" },
    baseFlip: { newItemAmount: 1e9, newItemBasePeriod: "",
                newItemMethod: "قیمت روز" },
    expDp: 10265165355.642443, expBar: 46771206401.056770 },
  { id: "D-16",
    flip: { ...NEW1E9, newItemMethod: "قیمت روز" },
    baseFlip: { ...NEW1E9, newItemMethod: "فهرست پیمان" },
    expDp: 10265165355.642443, expBar: 46771206401.056770 },
];

// اثرِ مورد انتظار (فلپ − پایه) به ریال: [dDeltaP, dBaravord]
const EFFECTS: Record<string, [number, number]> = {
  "D-01": [505316960.86, 0.0],
  "D-03": [-46869530.58, 0.0],
  "D-04": [0.0, 0.0],
  "D-08": [0.0, 0.0],
  "D-09": [0.0, 0.0],
  "D-10": [0.0, 0.0],
  "D-11": [-258322887.32, 734427471.64],
  "D-13": [-258322887.32, 734427471.64],
  "D-14": [309830097.09, 1470861083.46],
  "D-15": [280887947.43, 1333463580.73],
  "D-16": [-28942149.66, -137397502.73],
};

const BASE_DELTA_P = 9984277408.217051;
const BASE_BARAVORD = 45437742820.323151;

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
      (rows as unknown[]).push(
        ...parseDynamoMapping(toBuffer(path.join(sd, fn)), fn).rows);
    }
  }
  return computeProject(tables, OFFICIAL_1404_FEHREST, settings, {
    rows: rows as never,
    format: "v2",
    recordCount: rows.length,
    warnings: [],
  } as never);
}

function metrics(r: ProjectResult): [number, number] {
  const t = r.adjustment.tadil;
  const b = r.adjustment.baravord;
  return [t?.delta_p ?? 0, b?.result_amount ?? 0];
}

describe("T117 — اثرِ واقعیِ تصمیمات (پاریتی)", () => {
  it("اعدادِ پایهٔ مرجع", () => {
    const [dp, bar] = metrics(pipeline(baseSettings()));
    expect(dp).toBeCloseTo(BASE_DELTA_P, 6);
    expect(bar).toBeCloseTo(BASE_BARAVORD, 6);
  }, 120000);

  for (const sc of SCENARIOS) {
    it(`${sc.id} — ΔP و برآورد با عددِ ثابت مطابق است`, () => {
      const [dp, bar] = metrics(pipeline(baseSettings(sc.flip)));
      expect(dp).toBeCloseTo(sc.expDp, 6);
      expect(bar).toBeCloseTo(sc.expBar, 6);
    }, 120000);

    it(`${sc.id} — اثر = فلپ − پایه`, () => {
      const [dp, bar] = metrics(pipeline(baseSettings(sc.flip)));
      let refDp = BASE_DELTA_P;
      let refBar = BASE_BARAVORD;
      if (sc.baseFlip) {
        [refDp, refBar] = metrics(pipeline(baseSettings(sc.baseFlip)));
      }
      const [expDdp, expDbar] = EFFECTS[sc.id];
      expect(dp - refDp).toBeCloseTo(expDdp, 1);
      expect(bar - refBar).toBeCloseTo(expDbar, 1);
    }, 120000);
  }

  it("D-03 و D-13 صفر نیستند (ردِ مستنداتِ E-6)", () => {
    expect(EFFECTS["D-03"][0]).not.toBe(0);
    expect(EFFECTS["D-13"][0]).not.toBe(0);
    expect(EFFECTS["D-13"][1]).not.toBe(0);
  });

  it("D-18: اختلافِ دو سقفِ ۱۰٪", () => {
    const r = pipeline(baseSettings());
    expect(r.grandTotal * 1.1 - r.baseTotal * 1.1)
      .toBeCloseTo(8990157253.69, 1);
  }, 120000);
});
