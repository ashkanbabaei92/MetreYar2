import { describe, it, expect, beforeEach } from "vitest";
import { loadFixture, record } from "./helper";
import { parseRevitFile } from "../../src/lib/revitParser";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

describe("T01-T05 Revit Parse", () => {
  it("T01: R1 SIMPLE parse", () => {
    const text = loadFixture("revit/R1_simple.txt");
    const result = parseRevitFile("R1.txt", text);
    expect(record("T01", result, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T02: R2 TITLE+SUBTITLE parse", () => {
    const text = loadFixture("revit/R2_title_subtitle.txt");
    const result = parseRevitFile("R2.txt", text);
    expect(record("T02", result, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T03: R3 SUBTOTAL handling", () => {
    const text = loadFixture("revit/R3_subtotal.txt");
    const result = parseRevitFile("R3.txt", text);
    expect(record("T03", result, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T04: R4 UNKNOWN columns", () => {
    const text = loadFixture("revit/R4_unknown.txt");
    const result = parseRevitFile("R4.txt", text);
    expect(record("T04", result, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T05: R5 INCOMPLETE columns", () => {
    const text = loadFixture("revit/R5_incomplete.txt");
    const result = parseRevitFile("R5.txt", text);
    expect(record("T05", result, process.env.GENERATE === "1")).toBeDefined();
  });
});