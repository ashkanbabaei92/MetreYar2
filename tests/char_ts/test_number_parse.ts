import { describe, it, expect } from "vitest";
import { loadFixture, record } from "./helper";
import { parseValueUnit, toSI, toEnDigits, normalizeText } from "../../src/lib/normalize";
import { parseRevitFile } from "../../src/lib/revitParser";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

describe("T06-T13 Number Parse", () => {
  const inputs = [
    { id: "T06", val: "12.50" }, { id: "T07", val: "12,50" },
    { id: "T08", val: "1,250.75" }, { id: "T09", val: "1.250,75" },
    { id: "T10", val: "۱۲٫۵۰" }, { id: "T11", val: "12٬500" },
    { id: "T12", val: "1.250" }, { id: "T13", val: " 12.50 " },
  ];
  for (const { id, val } of inputs) {
    it(id + ": " + val, () => {
      const parsed = parseValueUnit(val);
      const si = parsed ? toSI(parsed.value, parsed.unit) : null;
      expect(record(id, { input: val, parse: parsed, si,
        persian_converted: toEnDigits(val) }, process.env.GENERATE === "1")).toBeDefined();
    });
  }
});