import { describe, it, expect, beforeEach } from "vitest";
import { record } from "./helper";
import { computeProject } from "../../src/lib/engine";
import { defaultSettings } from "../../src/lib/engine";
import { chapterTitle } from "../../src/data/fehrest";
import { rebarUnitWeight } from "../../src/lib/normalize";
import { moneyToWords } from "../../src/lib/farsi";
import { tokenSetRatio } from "../../src/lib/matching";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

describe("T31-T33 Financial", () => {
  it("T31: grand total rebalancing (TS no equivalent)", () => {
    expect(record("T31", { status: "UNMATCHED",
      note: "Python has grand total rebalancing; TS engine has no equivalent" },
      process.env.GENERATE === "1")).toBeDefined();
  });
});

describe("T42-T45 Utility", () => {
  it("T42: rebar weight table", () => {
    const weights: Record<number, number> = {};
    for (const d of [8, 14, 25, 36]) weights[d] = rebarUnitWeight(d);
    expect(record("T42", { weights }, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T43: chapter titles", () => {
    const chapters = ["01", "06", "07", "08", "10", "28"];
    const titles: Record<string, string> = {};
    for (const c of chapters) titles[c] = chapterTitle(c);
    expect(record("T43", { titles }, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T44: money to words", () => {
    const amounts = [0, 1000, 12345678, 1000000000];
    const results: Record<string, string> = {};
    for (const a of amounts) results[String(a)] = moneyToWords(a);
    expect(record("T44", { amounts: results }, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T45: TechnicalOfficeEngine parity", () => {
    const settings = defaultSettings();
    expect(record("T45", { settings_keys: Object.keys(settings),
      note: "Full parity test requires demo data via computeProject()" },
      process.env.GENERATE === "1")).toBeDefined();
  });
});

describe("T37-T38 Fuzzy", () => {
  it("T37: identical strings", () => {
    const results = [["بتن", "بتن"], ["Concrete", "Concrete"]].map(([a, b]) => ({
      a, b, score: tokenSetRatio(a, b),
    }));
    expect(record("T37", { results }, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T38: similar strings", () => {
    const inputs = [["بتن مگر", "بتن‌مگر"], ["قلب بندی", "قالب‌بندی"], ["میلگرد", "آرماتور"]];
    const results = inputs.map(([a, b]) => ({ a, b, score: tokenSetRatio(a, b) }));
    expect(record("T38", { results }, process.env.GENERATE === "1")).toBeDefined();
  });
});