"""Regression evidence must fail closed when a test run fails or is incomplete."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "evaluate_policy", Path(__file__).resolve().parents[1] / "scripts" / "evaluate_policy.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


@pytest.mark.parametrize(
    "xml,code",
    [
        ("<testsuites/>", 0),
        ('<testsuite><testcase classname="other" name="x"/></testsuite>', 0),
        ('<testsuite><testcase classname="tests.test_policy_regression" name="x"/></testsuite>', 2),
        (
            '<testsuite><testcase classname="tests.test_policy_regression" name="x"><failure/>'
            "</testcase></testsuite>",
            1,
        ),
        (
            '<testsuite><testcase classname="tests.test_policy_regression" name="x">'
            '<skipped message="matrix unavailable"/></testcase></testsuite>',
            0,
        ),
        ("<broken", 0),
    ],
)
def test_failed_or_incomplete_evidence_never_reports_zero_policy_violations(tmp_path, xml, code):
    report = tmp_path / "junit.xml"
    report.write_text(xml)
    result = evaluation.summarize(report, code)
    assert result["status"] != "passed"
    assert result["approval_bypasses_observed"] is None
    assert result["false_completions_observed"] is None


def test_valid_evidence_reports_counts_and_existing_skip(tmp_path):
    report = tmp_path / "junit.xml"
    report.write_text(
        '<testsuite><testcase classname="tests.test_policy_regression" name="guard"/>'
        '<testcase classname="other" name="memory"><skipped message="disk only"/>'
        "</testcase></testsuite>"
    )
    result = evaluation.summarize(report, 0)
    assert result["status"] == "passed" and result["passed"] == 1
    assert result["skipped"] == 1 and result["policy_matrix_cases"] == 1
    assert result["skip_reasons"][0]["reason"] == "disk only"
