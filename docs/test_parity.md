# حسابرسی پاریتی تست‌ها — Python در برابر TypeScript

تاریخ: ۱۴۰۵/۰۷/۱۴ (تحویلِ Parts C/D/E فاز E-6). منبعِ اعداد: خروجیِ رسمیِ
خودِ runnerها (`pytest --collect-only -q` و خروجیِ per-fileِ vitest).

- **Python:** ۷۵۶ test در ۶۳ فایل (۷۵۵ passed + ۱ xfailed از T111).
- **TypeScript:** ۷۳۰ test در ۶۲ فایل (۷۲۹ passed + ۱ expected fail از T111).
- **Δ = +۲۶ (py بیشتر).**

قاعده: پاریتی روی **سناریوها و اعدادِ مرجع** سنجیده می‌شود، نه روی
برابریِ تعدادِ تست. pytest با `@pytest.mark.parametrize` یک تابع را به
چندین مورد می‌شکافد؛ vitest با `it()` صریح می‌نویسد. هر جفتِ T9x/T10x
سناریوهای یکسانی را با اعدادِ مرجعِ یکسان (bit-identical) می‌آزماید.

## جدول فایل به فایل

| فایل | py | ts | Δ | وضعیت | دلیل |
|---|---|---|---|---|---|
| test_T100_e6_base_index | ۲۵ | ۲۴ | +۱ | ⚠ | py با ۲ بلوکِ `@parametrize` حالت‌ها را می‌شکافد |
| test_T101_e6_delays | ۱۹ | ۱۹ | ۰ | ✅ | |
| test_T102_e6_contract_status | ۱۰ | ۱۰ | ۰ | ✅ | |
| test_T103_e6_provisional_diff | ۱۰ | ۱۰ | ۰ | ✅ | |
| test_T104_e6_index_chain | ۱۰ | ۱۰ | ۰ | ✅ | |
| test_T105_e6_new_work | ۱۲ | ۱۲ | ۰ | ✅ | |
| test_T106_e6_new_work_excel | ۵ | ۵ | ۰ | ✅ | |
| test_T107_money_path_smoke | ۲۰۶ | ۲۰۶ | ۰ | ✅ | ۱۵ موردِ هدفدار + ۱۹۲ ترکیب |
| test_T108_ceiling | ۷ | ۷ | ۰ | ✅ | |
| test_T109_manual_index_source | ۱۰ | ۱۰ | ۰ | ✅ | |
| test_T110_inputs_status_panel | ۵ | ۵ | ۰ | ✅ | |
| test_T97_e6_k_and_rounding | ۹ | ۱۰ | −۱ | ⚠ | ts یک `it` اضافی (مرزِ ROUND_HALF_UP) |
| test_T97_e6_reference_numbers | ۹ | ۹ | ۰ | ✅ | |
| test_T98_e6_dp_table | ۳۰ | ۸ | +۲۲ | ⚠ | py با ۶ `@parametrize` جدولِ ΔP کامل را می‌شکافد؛ ts همان سناریوها را در ۸ `it` دارد |
| test_T99_e6_partc_inputs | ۷ | ۵ | +۲ | ⚠ | py دو تابعِ round-trip پروفایل با `src` اضافه دارد |
| test_T88_floors_coef | ۱۹ | ۱۰ | +۹ | ⚠ | py با ۱ `@parametrize` + ۵ حلقه حالت‌ها را می‌شکافد |
| test_T91_adjustment_engines | ۷۳ | ۸۰ | −۷ | ⚠ | ts ۷ تستِ شیت‌های Excel + بلوکِ CPI دارد (py همتای آن در T53/T91 پخش است) |
| test_T92_phase_c | ۱۲ | ۱۴ | −۲ | ⚠ | ts دو `it` اضافی (بنرِ خطای Excel) |
| test_T93_jalali | ۲۲ | ۲۵ | −۳ | ⚠ | ts سه `it` اضافی (مرزهای گاه‌شماری جلالی) |
| test_T32_rebar_grand_total | ۲ | ۲ | ۰ | ✅ | |
| test_T56_fehrest_unit_fix | ۲۸ | ۲۸ | ۰ | ✅ | |
| test_T60_fuzzy_parity | ۲ | ۱ | +۱ | ⚠ | py یک تابعِ اضافی |
| test_T61_encoding | ۵ | ۴ | +۱ | ⚠ | py با حلقهٔ `for` زیرحالت می‌سازد |
| test_T62_demo_dataset | ۲ | ۲ | ۰ | ✅ | |
| test_T63_normalize_parity | ۲ | ۲ | ۰ | ✅ | |
| test_T64_strict_golden | ۳ | ۳ | ۰ | ✅ | |
| test_T65_excel_formula_parity | ۳ | ۳ | ۰ | ✅ | |
| test_T66_v2_comment_skip | ۳ | ۳ | ۰ | ✅ | |
| test_T67_surcharge_080311 | ۳ | ۳ | ۰ | ✅ | |
| test_T68_surcharge_080310 | ۴ | ۴ | ۰ | ✅ | |
| test_T69_surcharge_080304 | ۴ | ۴ | ۰ | ✅ | |
| test_T70_technical_assumptions | ۵ | ۵ | ۰ | ✅ | |
| test_T71_joist_floor_exclusion | ۷ | ۷ | ۰ | ✅ | |
| test_T78_waste_removed | ۴ | ۴ | ۰ | ✅ | |
| test_T79_joist_remnants | ۴ | ۴ | ۰ | ✅ | |
| test_T80_ch8_surcharge_audit | ۳ | ۳ | ۰ | ✅ | |
| test_T81_financial_chain | ۶ | ۶ | ۰ | ✅ | |
| test_T82_index_base_period | ۴ | ۴ | ۰ | ✅ | |
| test_T83_index_chapter_factor | ۲ | ۲ | ۰ | ✅ | |
| test_T84_index_provisional | ۳ | ۳ | ۰ | ✅ | |
| test_T85_index_missing_chapter | ۴ | ۴ | ۰ | ✅ | |
| test_T90_warnings_registry | ۷ | ۷ | ۰ | ✅ | |
| test_T94_rebar_listoff | ۷ | ۷ | ۰ | ✅ | |
| test_T95_manual_prices | ۱۴ | ۱۴ | ۰ | ✅ | |
| test_T96_project_profile | ۱۹ | ۱۹ | ۰ | ✅ | |
| test_contract_foundation_precedence | ۶ | ۴ | +۲ | ⚠ | py دو تابعِ اضافی |
| test_excel | ۳ | ۳ | ۰ | ✅ | |
| test_financial | ۵ | ۷ | −۲ | ⚠ | ts دو `it` اضافی |
| test_idempotency | ۳ | ۳ | ۰ | ✅ | |
| test_mapping | ۷ | ۷ | ۰ | ✅ | |
| test_normalize | ۸ | ۸ | ۰ | ✅ | |
| test_number_parse | ۸ | ۸ | ۰ | ✅ | |
| test_rebar | ۷ | ۷ | ۰ | ✅ | |
| test_revit_parse | ۷ | ۵ | +۲ | ⚠ | py دو تابعِ اضافی (فایل‌های نمونهٔ بیشتر) |
| test_T107b_cpi_stop | ۰ | ۳ | −۳ | — | فقط ts: توقفِ CPI با `vi.mock` (py همتای آن داخلِ T91) |
| test_T55_mapping_rebar | ۰ | ۵ | −۵ | — | فقط ts: نگاشت میلگرد |
| test_doubled_quote | ۰ | ۲ | −۲ | — | فقط ts |
| test_engine_multifile | ۰ | ۹ | −۹ | — | فقط ts: چندفایلیِ موتور |
| test_engine_parity | ۰ | ۱۱ | −۱۱ | — | فقط ts: پاریتی موتور |
| test_parity_all10 | ۰ | ۱۱ | −۱۱ | — | فقط ts: پاریتی ۱۰ فایل |
| test_T53_e2e_pipeline | ۶ | ۰ | +۶ | — | فقط py: E2E خطِ لوله |
| test_T54_mapping_dedup | ۵ | ۰ | +۵ | — | فقط py: dedup نگاشت |
| test_T86_strength_map | ۱۷ | ۰ | +۱۷ | — | فقط py: نقشهٔ مقاومت (دادهٔ فیزیکی) |
| test_T87_slab_formwork | ۵ | ۰ | +۵ | — | فقط py: قالب‌بندی دال |
| test_T89_regional_coef | ۵ | ۰ | +۵ | — | فقط py: ضریب منطقه‌ای |
| test_fuzzy | ۳ | ۰ | +۳ | — | فقط py: فازی |
| test_number_batch | ۱ | ۰ | +۱ | — | فقط py: batch عدد |
| test_T111_issues_15_18 | ۴ (۳+xfail) | ۴ (۳+xfail) | ۰ | ✅ | Issues ۱۵–۱۸: جایگاهِ xfail تا رسیدنِ سند |
| test_T112_quality_parity | ۶ | ۶ | ۰ | ✅ | Part E شکاف ۷: پاریتیِ معیارهای quality + زنجیرهٔ مالی + mapping |
| **جمع** | **۷۵۶** | **۷۳۰** | **+۲۶** | | |

## نتیجه

هیچ جفتِ تستِ E-6ای وجود ندارد که در یک زبان باشد و در زبانِ دیگر نباشد
(هر ۱۶ فایلِ T97–T110 در هر دو زبان هست). ۱۲ جفت تعدادشان برابر است و
۴ جفت (T97-k، T98، T99، T88) به‌خاطرِ parametrize در py اختلافِ شمارش
دارند ولی سناریوها را یکسان می‌پوشانند. فایل‌های تک‌زبانه متعلق به
فازهای پیشین هستند (E2E، دادهٔ فیزیکی، پاریتیِ خالص) و در E-6 افزوده
نشده‌اند.
