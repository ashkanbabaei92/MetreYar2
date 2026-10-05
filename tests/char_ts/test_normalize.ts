import { describe, it, expect, beforeEach } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { record } from "./helper";
import { normalizeText, toEnDigits, toSI, parseValueUnit, confLabel } from "../../src/lib/normalize";
import { parseRevitFile } from "../../src/lib/revitParser";
import { searchFehrest } from "../../src/lib/matching";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

describe("T24-T30 Normalize", () => {
  it("T24: kind classification", () => {
    const kinds = ["lean_concrete", "structural_concrete", "formwork_foundation", "joist_floor"];
    const results: any = {};
    for (const k of kinds) {
      const fname = path.join(__dirname, "fixtures", "revit", `${k}.txt`);
      results[k] = { has_fixture: fs.existsSync(fname) };
    }
    expect(record("T24", results, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T25: mm→m", () => {
    expect(record("T25", { input: [1000, "mm"], result: toSI(1000, "mm") },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T26: cm→m", () => {
    expect(record("T26", { input: [100, "cm"], result: toSI(100, "cm") },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T27: ton→kg", () => {
    expect(record("T27", { input: [1, "ton"], result: toSI(1, "ton") },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T28: Persian digits", () => {
    const inputs = ["۱۲٫۵۰", "۱۲۳", "۰"];
    const results: any = {};
    for (const inp of inputs) {
      results[inp] = { toEnDigits: toEnDigits(inp), normalize: normalizeText(inp) };
    }
    expect(record("T28", results, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T29: stop words", () => {
    const inputs = ["و بتن و سازه به در", "سقف تیرچه بلوک"];
    const results: any = {};
    for (const inp of inputs) {
      results[inp] = { normalized: normalizeText(inp) };
    }
    expect(record("T29", results, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T30: Arabic chars", () => {
    const inputs = ["كلمات عربى", "إلى أبتداء"];
    const results: any = {};
    for (const inp of inputs) {
      results[inp] = { original: inp, normalized: normalizeText(inp),
        toEnDigits: toEnDigits(inp) };
    }
    expect(record("T30", results, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T54: ZWNJ kind classification (parity with app.py)", () => {
    const z = "\u200c"; // نیم‌فاصله
    const superFormwork =
      `"جدول ریزمتره قالب${z}بندی اسکلت - Superstructure Formwork Schedule","","",""\n` +
      '"Category","Family and Type","Material: Name","Material: Area"\n' +
      '"Structural Columns","M_Concrete-Rectangular-Column: C45X60-20F20","CONCRETE","53 m²"\n';
    const sf = parseRevitFile("sf.txt", superFormwork);
    expect(sf.kind).toBe("formwork_super");
    expect(sf.kindConfidence).toBeCloseTo(0.95, 5);
    expect(sf.rows.length).toBe(1);

    const foundationConcrete =
      `"جدول بتن${z}ریزی پی - Foundation Concrete Schedule","","","",""\n` +
      '"Mark","Family and Type","Length","Volume","Area"\n' +
      '"FT-L(1-2)","Wall Foundation: WF_A_1800x900","13471.04 mm","21.82 m³","24.25 m²"\n';
    const fc = parseRevitFile("fc.txt", foundationConcrete);
    expect(fc.kind).toBe("structural_concrete");
    expect(fc.kindConfidence).toBeCloseTo(0.97, 5);
    expect(fc.rows.length).toBe(1);
  });
});