"""Regression tests cho trace case (docs/trace_case.md). Chạy: python -m pytest -q -m student -o addopts= -k lab9"""
import pytest

pytestmark = pytest.mark.student


def _ctx(trial, label):
    from pydantic_evals.evaluators import EvaluatorContext

    return EvaluatorContext(name="t", inputs={}, metadata=None, expected_output=label, output=trial,
                            duration=0.0, _span_tree=None, attributes={}, metrics={})


def _case(shape, claim, seed=11):
    from lab9.trace_case import investigate

    return investigate(shape, claim, seed)


def test_c002_seeded_first_wrong_step_is_model_override():
    """FM-03: bước sai đầu tiên là event model_override (ticket đè delay_days của DB)."""
    from lab9.graders import DbFactKept, RefundAmountCorrect

    case = _case("seeded_regression", "C-002")
    kinds = [e["kind"] for e in case["trial"]["events"]]
    assert kinds.index("model_override") == 2            # event thứ 3 trong trace
    ctx = _ctx(case["trial"], case["label"])
    assert RefundAmountCorrect().evaluate(ctx).value is False   # ledger 20.000 thay vì 0
    assert DbFactKept().evaluate(ctx).value is False


def test_c002_fixed_keeps_db_fact():
    from lab9.graders import DbFactKept, RefundAmountCorrect

    case = _case("fixed", "C-002")
    ctx = _ctx(case["trial"], case["label"])
    assert "model_override" not in [e["kind"] for e in case["trial"]["events"]]
    assert RefundAmountCorrect().evaluate(ctx).value is True
    assert DbFactKept().evaluate(ctx).value is True


def test_c008_misreport_only_caught_by_reply_matches_ledger():
    """FM-05/FM-08: Lab 8 grader vẫn PASS (ledger đúng 20.000đ) nhưng reply báo 35.000đ."""
    from lab9.graders import ReplyMatchesLedger

    bad = _case("seeded_regression", "C-008")
    assert bad["trial"]["lab8_pass"] is True
    assert ReplyMatchesLedger().evaluate(_ctx(bad["trial"], bad["label"])).value is False
    good = _case("fixed", "C-008")
    assert ReplyMatchesLedger().evaluate(_ctx(good["trial"], good["label"])).value is True
