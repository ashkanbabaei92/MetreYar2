import { describe, it, expect } from "vitest";
import { loadJson, loadJsonFixture, record } from "./helper";
import { searchFehrest, byCode, tokenSetRatio, fuzzyScore } from "../../src/lib/matching";
import { normalizeText, parseValueUnit, toSI, toEnDigits } from "../../src/lib/normalize";
import { rebarUnitWeight, confLabel } from "../../src/lib/normalize";
import { computeProject, directCodedLines, defaultSettings } from "../../src/lib/engine";
import type { MappingData, MappingRow, FehrestRow } from "../../src/lib/types";

let uuidCounter = 0;
beforeEach(() => {
  uuidCounter = 0;
  (crypto as any).randomUUID = () => `mock-uuid-${uuidCounter++}`;
});

describe("T14-T19 Mapping", () => {
  it("T14: direct coded lines — قرارداد مشترک از fixture شارژشده", () => {
    // fixture مشترک: تنها منبع حقیقت برای T14 در هر دو زبان (بدون وابستگی به golden)
    const path = require("path");
    const fx = loadJson(path.join(__dirname, "..", "char_shared", "fixtures", "mapping", "T14_direct_coded.json"));

    const rows = fx.mapping.rows as MappingRow[];
    const db = fx.fehrest_db as FehrestRow[];
    const settings = { ...defaultSettings(), ...fx.settings };
    const lines = directCodedLines({ ...fx.mapping, rows } as MappingData, db, settings);

    // سازگاری خودِ fixture با قراردادش
    expect(fx.mapping.recordCount).toBe(rows.length);
    expect(fx.expected.length).toBe(fx.meta.expected_line_count);
    expect(fx.tolerance.rtol).toBeGreaterThan(0);
    expect(fx.tolerance.atol).toBeGreaterThan(0);

    const exclude = new Set<string>(fx.exclude_fields ?? []);
    const aliases: Record<string, string> = fx.field_aliases ?? {};
    const aliasOf = (field: string) => aliases[field] ?? field;
    const rtol: number = fx.tolerance.rtol;
    const atol: number = fx.tolerance.atol;

    // source_format ویژگی گروه است نه فیلد خط؛ از انتهای id استخراج می‌شود
    const valueOf = (line: any, field: string) =>
      field === "source_format"
        ? String(line.id).slice(String(line.id).lastIndexOf("-") + 1)
        : line[aliasOf(field)];

    const actualById = new Map<string, any>();
    for (const l of lines as any[]) {
      const copy: any = { ...l };
      for (const k of exclude) delete copy[k];
      actualById.set(l.id, copy);
    }
    const expectedIds = (fx.expected as any[]).map((e) => e.id);

    const problems: string[] = [];

    // (۱) مجموعهٔ idها باید دقیقاً برابر قرارداد باشد (خط اضافه یا کم‌شده شکست می‌دهد)
    const actualIds = [...actualById.keys()].sort();
    const wantIds = [...expectedIds].sort();
    if (JSON.stringify(actualIds) !== JSON.stringify(wantIds)) {
      problems.push(
        `ID_SET: خط ناخواسته ${JSON.stringify(actualIds.filter((x) => !expectedIds.includes(x)))}` +
        ` — خط تولیدنشده ${JSON.stringify(wantIds.filter((x) => !actualById.has(x)))}`,
      );
    }

    // (۲) مقایسهٔ فیلدبه‌فیلد با تلورانس عددی fixture
    const mismatches: string[] = [];
    for (const want of fx.expected as any[]) {
      const actual = actualById.get(want.id);
      if (!actual) { mismatches.push(`${want.id}: خط تولید نشد`); continue; }
      for (const field of fx.compare_fields as string[]) {
        if (field === "id") continue;
        const w = want[field];
        const g = valueOf(actual, field);
        if (typeof w === "number") {
          const tol = atol + rtol * Math.abs(w);
          if (typeof g !== "number" || !Number.isFinite(g) || Math.abs(g - w) > tol)
            mismatches.push(`${want.id}.${field}: انتظار ${w} — دریافت ${String(g)}`);
        } else if (JSON.stringify(w) !== JSON.stringify(g ?? null)) {
          mismatches.push(`${want.id}.${field}: انتظار ${JSON.stringify(w)} — دریافت ${JSON.stringify(g ?? null)}`);
        }
      }
    }
    problems.push(...mismatches);

    // (۳) not_expected: هیچ‌یک از این کدها نباید خط تولید کند
    const producedCodes = new Set(lines.map((l) => l.code));
    problems.push(
      ...(fx.not_expected as any[])
        .filter((n) => producedCodes.has(n.fehrest_code))
        .map((n) => `NOT_EXPECTED: ${n.element_id} (${JSON.stringify(n.fehrest_code)}) — ${n.reason}`),
    );

    // (۴) cases: هر case فقط با دادهٔ fixture سنجیده می‌شود (divergenceهای A-1..A-4 را آشکار می‌کند)
    const byElement = new Map<string, any>(rows.map((r) => [r.element_id, r]));
    const caseFailures: string[] = [];
    for (const c of fx.cases as any[]) {
      const derived = new Set<string>();
      for (const elementId of c.rows as string[]) {
        const r = byElement.get(elementId);
        if (!r) { caseFailures.push(`${c.case}: ردیف ${elementId} در fixture نیست`); continue; }
        derived.add(`direct-${String(r.fehrest_code ?? "").trim()}-${r.source_format ?? "v2"}`);
      }
      const fix = c.fix ? ` (نیازمند ${c.fix})` : "";
      for (const id of c.expect_lines as string[]) {
        if (!actualById.has(id)) caseFailures.push(`[${c.case}] انتظار خط ${id} — تولید نشد${fix}`);
      }
      for (const id of derived) {
        if (!(c.expect_lines as string[]).includes(id) && actualById.has(id))
          caseFailures.push(`[${c.case}] خط ناخواسته ${id}${fix}`);
      }
    }
    problems.push(...caseFailures);

    // تنها اِسِرت نهایی: تمام divergenceها در یک اجرا گزارش می‌شوند
    expect(problems).toEqual([]);
  });
  it("T20: exact estimated plan honors an explicit zero override", () => {
    const db: FehrestRow[] = [{
      code: "080102", chapter: "08", desc: "بتن با ۱۵۰ کیلوگرم سیمان", unit: "مترمکعب",
      price: 17152000, estimated: true,
    }];
    const settings = { ...defaultSettings(), priceOverrides: { lean: 0 } };
    const table: any = {
      id: "lean-table", fileName: "lean.txt", title: "Lean",
      headers: [], rows: [{ cells: [], values: { volume: 10 }, texts: {}, isSubtotal: false }],
      kind: "lean_concrete", kindConfidence: 0.97, colMap: {}, warnings: [],
    };
    const line = computeProject([table], db, settings).lines.find((item) => item.id === "lean");

    expect(line).toBeDefined();
    expect(line?.matchMethod).toBe("rule-exact");
    expect(line?.price).toBe(0);
    expect(line?.estimatedPrice).toBe(false);
    expect(line?.needsReview).toBe(false);
  });
  it("T15: exact match", () => {
    const data = loadJsonFixture("mapping/parity.json");
    const db = data.fehrest_db;
    const results: any[] = [];
    for (const row of data.mapping.rows.slice(0, 3)) {
      const code = row.fehrest_code;
      if (code) {
        const exact = byCode(db, code);
        results.push({ code, found: !!exact, desc: exact?.desc ?? null });
      }
    }
    expect(record("T15", { results }, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T16: fuzzy match", () => {
    const data = loadJsonFixture("mapping/parity.json");
    const db = data.fehrest_db;
    const results: any[] = [];
    for (const row of data.mapping.rows.slice(0, 3)) {
      const code = row.fehrest_code;
      if (code) {
        const candidates = searchFehrest(db, `ردیف ${code}`, { top: 3, minScore: 0.3 });
        results.push({ code, candidates: candidates.map((c) => ({ code: c.row.code, score: c.score })) });
      }
    }
    expect(record("T16", { results }, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T17: estimated flags", () => {
    const data = loadJsonFixture("mapping/parity.json");
    const results = data.fehrest_db.map((r: any) => ({ code: r.code, estimated: r.estimated ?? false }));
    expect(record("T17", { results }, process.env.GENERATE === "1")).toBeDefined();
  });
  it("T18: no match", () => {
    const data = loadJsonFixture("mapping/parity.json");
    const result = fuzzyScore("zzz_no_match_12345", data.fehrest_db[0].desc);
    expect(record("T18", { query: "zzz_no_match_12345", score: result },
      process.env.GENERATE === "1")).toBeDefined();
  });
  it("T19: manual override", () => {
    const data = loadJsonFixture("mapping/parity.json");
    const db = data.fehrest_db;
    const code = "080201";
    const row = byCode(db, code);
    expect(record("T19", { code, found: !!row, desc: row?.desc ?? null,
      note: "Manual override tested via UI only" }, process.env.GENERATE === "1")).toBeDefined();
  });
});