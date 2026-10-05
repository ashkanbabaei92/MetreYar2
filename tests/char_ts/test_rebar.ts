import { describe, it, expect, beforeEach } from "vitest";
import { record } from "./helper";
import { rebarUnitWeight } from "../../src/lib/normalize";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import { EMBEDDED_FEHREST } from "../../src/data/fehrest";
import type { RevitTable } from "../../src/lib/types";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

describe("T20-T23 Rebar Weight", () => {
  it("T20: Φ8", () => {
    expect(record("T20", { input: 8, weight: rebarUnitWeight(8) },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T21: Φ14", () => {
    expect(record("T21", { input: 14, weight: rebarUnitWeight(14) },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T22: Φ25", () => {
    expect(record("T22", { input: 25, weight: rebarUnitWeight(25) },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T23: Φ36", () => {
    expect(record("T23", { input: 36, weight: rebarUnitWeight(36) },
      process.env.GENERATE === "1")).toBeDefined();
  });
});

// ── مرزهای واحد قطر آرماتور (mm): ≤10 → 070201 ، ۱۲–۱۸ → 070202 ، ≥۲۰ → 070203 ──

/** ردیف آرماتور با قطر بر حسب متر (خروجی toSI از ستون «Bar Diameter») */
function rebarRowMeters(diameterM: number, weight = 1) {
  return {
    cells: [],
    values: { weight, diameter: diameterM },
    texts: { material: "IR-Rebar-Fy4000" },
    isSubtotal: false,
  };
}

/** ردیف آرماتور بدون ستون قطر — مسیر fallback: قطر از متن Φn استخراج می‌شود (mm) */
function rebarRowFallback(diameterMm: number, weight = 1) {
  return {
    cells: [],
    values: { weight },
    texts: { barType: `Φ${diameterMm}`, material: `Φ${diameterMm} IR-Rebar-Fy4000` },
    isSubtotal: false,
  };
}

function bucketCodes(rows: any[]): Record<string, number> {
  const table = {
    id: "synthetic",
    fileName: "synthetic.txt",
    title: "Synthetic Rebar",
    headers: ["Bar Diameter", "Weight (kg)"],
    rows,
    kind: "rebar_detailed",
    kindConfidence: 1,
    colMap: { diameter: 0, weight: 1 },
    warnings: [],
  } as unknown as RevitTable;
  const result = computeProject([table], EMBEDDED_FEHREST, defaultSettings());
  const out: Record<string, number> = {};
  for (const l of result.lines) {
    if (l.code.startsWith("0702")) out[l.code] = (out[l.code] || 0) + l.qty;
  }
  return out;
}

describe("T24-T26 Rebar bucket unit boundaries", () => {
  it("T24: meters input — 10mm → 070201 / 10.01mm → 070202 / 18mm → 070202 / 18.01mm → 070203", () => {
    expect(bucketCodes([rebarRowMeters(0.01)])).toEqual({ "070201": 1 });
    expect(bucketCodes([rebarRowMeters(0.01001)])).toEqual({ "070202": 1 });
    expect(bucketCodes([rebarRowMeters(0.018)])).toEqual({ "070202": 1 });
    expect(bucketCodes([rebarRowMeters(0.01801)])).toEqual({ "070203": 1 });
  });

  it("T25: fallback mm input — same boundaries (Φ16 → 070202)", () => {
    expect(bucketCodes([rebarRowFallback(10)])).toEqual({ "070201": 1 });
    expect(bucketCodes([rebarRowFallback(16)])).toEqual({ "070202": 1 });
    expect(bucketCodes([rebarRowFallback(20)])).toEqual({ "070203": 1 });
  });

  it("T26: plain grade (AI/2400) → 070101 regardless of diameter", () => {
    const table = {
      id: "synthetic-plain",
      fileName: "synthetic.txt",
      title: "Synthetic Rebar",
      headers: ["Bar Diameter", "Weight (kg)"],
      rows: [{
        cells: [],
        values: { weight: 1, diameter: 0.02 },
        texts: { material: "IR-Rebar-Fy2400" },
        isSubtotal: false,
      }],
      kind: "rebar_detailed",
      kindConfidence: 1,
      colMap: { diameter: 0, weight: 1 },
      warnings: [],
    } as unknown as RevitTable;
    const result = computeProject([table], EMBEDDED_FEHREST, defaultSettings());
    expect(result.lines.find((l) => l.code === "070101")?.qty).toBe(1);
  });
});
