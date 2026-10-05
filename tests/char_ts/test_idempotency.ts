import { describe, it, expect } from "vitest";
import { record } from "./helper";
import { parseRevitFile } from "../../src/lib/revitParser";
import { RevitTable } from "../../src/lib/types";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

describe("T39-T41 Idempotency & Dedup", () => {
  it("T39: idempotency re-parse", () => {
    const fs = require("fs");
    const path = require("path");
    const text = fs.readFileSync(path.join(__dirname, "fixtures", "revit", "R1_simple.txt"), "utf-8");
    const excludeId = (r: any) => { const { id, ...rest } = r; return rest; };
    const r1 = excludeId(parseRevitFile("R1.txt", text));
    const r2 = excludeId(parseRevitFile("R1.txt", text));
    expect(record("T39", { r1_headers: r1.headers, r2_headers: r2.headers,
      identical: JSON.stringify(r1) === JSON.stringify(r2) },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T40: dedup repeated row", () => {
    const fs = require("fs");
    const path = require("path");
    const text = fs.readFileSync(path.join(__dirname, "fixtures", "revit", "R3_subtotal.txt"), "utf-8");
    const excludeId = (r: any) => { const { id, ...rest } = r; return rest; };
    const result = excludeId(parseRevitFile("R3.txt", text));
    const subtotalRows = result.rows.filter((r: any) => r.isSubtotal);
    const dataRows = result.rows.filter((r: any) => !r.isSubtotal);
    expect(record("T40", { total_rows: result.rows.length,
      subtotal_rows: subtotalRows.length, data_rows: dataRows.length,
      subtotal_content: subtotalRows.map((r: any) => r.texts) },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T41: dedup same values diff elements", () => {
    const fs = require("fs");
    const path = require("path");
    const text = fs.readFileSync(path.join(__dirname, "fixtures", "revit", "R2_title_subtitle.txt"), "utf-8");
    const excludeId = (r: any) => { const { id, ...rest } = r; return rest; };
    const result = excludeId(parseRevitFile("R2.txt", text));
    expect(record("T41", { total_rows: result.rows.length,
      rows_detail: result.rows.map((r: any) => ({ values: r.values, texts: r.texts,
        isSubtotal: r.isSubtotal })) },
      process.env.GENERATE === "1")).toBeDefined();
  });
});