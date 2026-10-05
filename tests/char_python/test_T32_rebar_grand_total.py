import copy

import pytest

from app import FehrestBahaParser, TechnicalOfficeEngine, default_settings
from helper import load_json_fixture


FIXTURE = load_json_fixture("..", "..", "char_shared", "fixtures", "revit", "T32_rebar_grand_total.json")


def summarize(case_name):
    expected = FIXTURE["expected"][case_name]
    table = copy.deepcopy(FIXTURE["table"])
    table["grand_total"] = {"weight": expected["grand_total_weight"]}
    settings = default_settings()
    settings["overhead_coef"] = FIXTURE["settings"]["overhead_coef"]
    settings["regional_coef"] = FIXTURE["settings"]["regional_coef"]
    settings["floors_coef"] = FIXTURE["settings"]["floors_coef"]
    settings["site_setup_amount"] = FIXTURE["settings"]["site_setup_amount"]
    settings["insurance_pct"] = FIXTURE["settings"]["insurance_pct"]
    settings["tax_pct"] = FIXTURE["settings"]["tax_pct"]
    settings["good_job_pct"] = FIXTURE["settings"]["good_job_pct"]
    settings["advance_payment"] = FIXTURE["settings"]["advance_payment"]
    engine = TechnicalOfficeEngine(FIXTURE["db"], settings)
    result = engine.compute([table], None)
    by_code = {line["code"]: line for line in result["lines"]}
    return result, by_code, expected


def assert_case(case_name):
    result, by_code, expected = summarize(case_name)
    assert sum(
        row["values"].get("weight", 0)
        for row in FIXTURE["table"]["rows"]
        if not row["is_subtotal"] and row["values"].get("weight", 0) > 0
    ) == expected["rows_sum"]
    assert expected["grand_total_weight"] <= expected["rows_sum"] * FIXTURE["meta"]["threshold"] or expected["reconciled"]

    assert len(result["quality"]["warnings"]) == expected["warning_count"]
    for code, line_expected in expected["rebar_lines"].items():
        line = by_code[code]
        assert line["qty"] == pytest.approx(line_expected["qty"])
        assert line["total"] == pytest.approx(line_expected["total"])

    transport = by_code["280101"]
    assert transport["qty"] == pytest.approx(expected["transport"]["qty"])
    assert transport["total"] == pytest.approx(expected["transport"]["total"])
    assert result["base_total"] == pytest.approx(expected["base_total"])
    assert result["grand_total"] == pytest.approx(expected["grand_total"])
    assert result["net_payable"] == pytest.approx(expected["net_payable"])


def test_T32_reconcile_above_threshold():
    assert_case("reconcile_above_threshold")


def test_T32_boundary_at_threshold():
    assert_case("boundary_at_threshold")
