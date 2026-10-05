import { describe, it, expect, beforeEach } from "vitest";
import { parseRevitFile, structuralGroup } from "../../src/lib/revitParser";
import { foundationCandidates } from "../../src/lib/engine";
import type { QuantityRecord, RevitTable, TableKind } from "../../src/lib/types";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

const rec = (
  fileName: string,
  ref: string,
  kind: TableKind,
  qty: number,
  group: string,
): QuantityRecord => ({
  tableId: `t-${fileName}`, fileName, tableTitle: fileName, kind, ref, group,
  material: "", qty, unit: "m3", detail: "",
});

const formworkTable = (rows: [string, string, number][]): RevitTable => ({
  id: "fw", fileName: "FW.txt", title: "Foundation Formwork", headers: [],
  kind: "formwork_foundation", kindConfidence: 0.97, colMap: {}, warnings: [],
  rows: rows.map(([mark, familyType, length]) => ({
    cells: [], values: { length }, texts: { mark, familyType }, isSubtotal: false,
  })),
});

describe("G1 foundation source precedence (parity with app.py)", () => {
  it("dedups per ref: dedicated table wins, lean refs excluded, derived fills gaps", () => {
    const records: QuantityRecord[] = [
      rec("FC.txt", "FT-1", "structural_concrete", 10, "پی"),
      rec("FC.txt", "FT-2", "structural_concrete", 20, "پی"),
      rec("SC.txt", "FT-1", "structural_concrete", 10, "پی"),
      rec("SC.txt", "FT-2", "structural_concrete", 20, "پی"),
      rec("SC.txt", "LC-9", "structural_concrete", 5, "پی"),
      rec("SC.txt", "C1", "structural_concrete", 7, "پله"),
      rec("LC.txt", "LC-9", "lean_concrete", 5, "پی"),
    ];
    const tables = [
      formworkTable([
        ["FT-1", "Wall Foundation: WF_A_1800x900", 10],
        ["FT-2", "Wall Foundation: WF_A_2000x1000", 5],
        ["FT-9", "Wall Foundation: WF_A_1000x1000", 3],
      ]),
    ];
    const { direct, derived } = foundationCandidates(records, tables);
    expect(direct.map((r) => r.ref).sort()).toEqual(["FT-1", "FT-2"]);
    expect(new Set(direct.map((r) => r.fileName))).toEqual(new Set(["FC.txt"]));
    expect(direct.reduce((a, r) => a + r.qty, 0)).toBeCloseTo(30, 6);
    expect(derived.map((r) => r.ref)).toEqual(["FT-9"]);
    expect(derived[0].qty).toBeCloseTo(3, 6);
  });

  it("uses derived values only when no direct source exists", () => {
    const tables = [formworkTable([["FT-1", "Wall Foundation: WF_A_1800x900", 10]])];
    const { direct, derived } = foundationCandidates([], tables);
    expect(direct.length).toBe(0);
    expect(derived.length).toBe(1);
    expect(derived[0].qty).toBeCloseTo(16.2, 6);
  });
});

describe("G3 STRUCTURAL is not stair (parity with app.py)", () => {
  it("keeps STR marks as stair and STRUCTURAL as column/beam", () => {
    expect(structuralGroup(
      "C01-ST01 M_Concrete-Rectangular-Column: C45X60-20F20 Structural Columns",
      "structural_concrete")).toBe("ستون");
    expect(structuralGroup(
      "B01-ST01 M_Concrete-Rectangular Beam: B45X50 Structural Framing",
      "structural_concrete")).toBe("تیر");
    expect(structuralGroup(
      "JSL-TOP01-ST01 Floor: Slab_Topping_50mm Floors", "structural_concrete")).toBe("سقف");
    expect(structuralGroup(
      "STR01-ST01 Cast-In-Place Stair: Monolithic Stair IRAN",
      "structural_concrete")).toBe("پله");
    expect(structuralGroup("STR-B1", "structural_concrete")).toBe("پله");
    expect(structuralGroup("FT-L(1-2) Wall Foundation: WF_A_1800x900",
      "structural_concrete")).toBe("پی");
  });
});

describe("G2 unlabeled total row (parity with app.py)", () => {
  it("treats a text-less numeric row as Grand total, not as a record", () => {
    const text = '"Sample Schedule","",""\n' +
      '"Mark","Family and Type","Volume"\n' +
      '"LC-01","Foundation Slab: 100mm","18.65 m³"\n' +
      '"","","18.65 m³"\n';
    const t = parseRevitFile("g2.txt", text);
    expect(t.rows.length).toBe(1);
    expect(t.grandTotal?.volume).toBeCloseTo(18.65, 6);
  });
});
