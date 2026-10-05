import { describe, expect, it } from "vitest";
import * as path from "path";
import { computeProject, defaultSettings } from "../../src/lib/engine";
import type { FehrestRow, RevitTable } from "../../src/lib/types";
import { loadJson } from "./helper";

const fixture = loadJson(path.join(__dirname, "..", "char_shared", "fixtures", "revit", "T32_rebar_grand_total.json"));

function summarize(caseName: string) {
  const expected = fixture.expected[caseName];
  const table = {
    ...fixture.table,
    fileName: fixture.table.file_name,
    kindConfidence: fixture.table.kind_confidence,
    colMap: fixture.table.col_map,
    grandTotal: { weight: expected.grand_total_weight },
    rows: fixture.table.rows.map((row: any) => ({
      ...row,
      isSubtotal: row.is_subtotal,
    })),
  } as RevitTable;
  const settings = {
    ...defaultSettings(),
    overheadCoef: fixture.settings.overhead_coef,
    regionalCoef: fixture.settings.regional_coef,
    floorsCoef: fixture.settings.floors_coef,
    siteSetupAmount: fixture.settings.site_setup_amount,
    insurancePct: fixture.settings.insurance_pct,
    taxPct: fixture.settings.tax_pct,
    goodJobPct: fixture.settings.good_job_pct,
    advancePayment: fixture.settings.advance_payment,
  };
  const result = computeProject(table ? [table] : [], fixture.db as FehrestRow[], settings);
  const byCode = new Map(result.lines.map((line) => [line.code, line]));
  return { result, byCode, expected };
}

function assertCase(caseName: string) {
  const { result, byCode, expected } = summarize(caseName);
  const rowsSum = fixture.table.rows
    .filter((row: any) => !row.is_subtotal && row.values.weight > 0)
    .reduce((sum: number, row: any) => sum + row.values.weight, 0);
  expect(rowsSum).toBe(expected.rows_sum);
  expect(expected.grand_total_weight > rowsSum * fixture.meta.threshold).toBe(expected.reconciled);
  expect(result.quality.warnings).toHaveLength(expected.warning_count);

  for (const [code, lineExpected] of Object.entries(expected.rebar_lines) as any[]) {
    const line = byCode.get(code);
    expect(line).toBeDefined();
    expect(line?.qty).toBeCloseTo(lineExpected.qty, 9);
    expect(line?.total).toBeCloseTo(lineExpected.total, 6);
  }

  const transport = byCode.get("280101");
  expect(transport?.qty).toBeCloseTo(expected.transport.qty, 9);
  expect(transport?.total).toBeCloseTo(expected.transport.total, 6);
  expect(result.baseTotal).toBeCloseTo(expected.base_total, 6);
  expect(result.grandTotal).toBeCloseTo(expected.grand_total, 6);
  expect(result.netPayable).toBeCloseTo(expected.net_payable, 6);
}

describe("T32 Rebar Grand Total reconciliation", () => {
  it("reconciles when Grand Total exceeds the 2% threshold", () => {
    assertCase("reconcile_above_threshold");
  });

  it("does not reconcile at the 2% threshold", () => {
    assertCase("boundary_at_threshold");
  });
});
