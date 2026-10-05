import { defineConfig } from "vitest/config";

// پیکربندیِ تست‌های سریعِ TypeScript (فاز E-۷ بخش ۴).
//
// این فایل فقط شیفتی از vitest.config.ts است که ۳۰ فایلِ «slow» را خارج
// می‌کند — یعنی همان فایل‌هایی که خطِ لولهٔ کاملِ Revit را اجرا می‌کنند
// (آینهٔ `pytestmark = pytest.mark.slow` در tests/char_python). این ۵ فایلِ
// کندِ پایتون که همتای TS ندارند اینجا نیازی نیست ذکر شوند.
//
// اجرا:  npx vitest run --config vitest.fast.config.ts
//        (به‌طور پیش‌فرض با run_fast_tests.ps1)

const SLOW_TS = [
  "test_contract_foundation_precedence",
  "test_T106_e6_new_work_excel",
  "test_T110_inputs_status_panel",
  "test_T113_baravord_reference_numbers",
  "test_T114_excel_currency_units",
  "test_T56_fehrest_unit_fix",
  "test_T62_demo_dataset",
  "test_T65_excel_formula_parity",
  "test_T66_v2_comment_skip",
  "test_T67_surcharge_080311",
  "test_T68_surcharge_080310",
  "test_T69_surcharge_080304",
  "test_T70_technical_assumptions",
  "test_T71_joist_floor_exclusion",
  "test_T78_waste_removed",
  "test_T79_joist_remnants",
  "test_T80_ch8_surcharge_audit",
  "test_T81_financial_chain",
  "test_T82_index_base_period",
  "test_T83_index_chapter_factor",
  "test_T84_index_provisional",
  "test_T85_index_missing_chapter",
  "test_T88_floors_coef",
  "test_T90_warnings_registry",
  "test_T91_adjustment_engines",
  "test_T94_rebar_listoff",
  "test_T97_e6_k_and_rounding",
  "test_T97_e6_reference_numbers",
  "test_T98_e6_dp_table",
  "test_T99_e6_partc_inputs",
].map((n) => `tests/char_ts/${n}.ts`);

export default defineConfig({
  test: {
    include: ["tests/char_ts/test_*.ts"],
    exclude: SLOW_TS,
    setupFiles: ["tests/char_ts/setup.ts"],
    globals: true,
    testTimeout: 60_000,
  },
});
