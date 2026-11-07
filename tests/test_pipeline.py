"""Offline tests: the deterministic facts, the validation rules, the statistics tools and the agent loop (fake client)."""

import json
from types import SimpleNamespace

import pandas as pd
import pytest

from adp import facts
from adp.llm import Claude, LLMError, Usage
from adp.tools import Toolbox

KEY = ["year", "commune"]


@pytest.fixture
def df():
    return pd.DataFrame({
        "year": ["2024", "2024", "2024", "2025", "2025", "2025"],
        "commune": ["Alpha", "Beta", "Gamma", "Alpha", "Beta", "Beta"],
        "n_listings": ["100", "12", "50", "120", "10", "10"],
        "avg_price_eur": ["500000", "*", "900000", "600000", "*", "*"],
        "avg_price_per_m2_eur": ["5000", "*", "9000", "6000", "*", "*"],
    })


def test_quality_finds_placeholders_and_duplicate_keys(df):
    q = facts.quality(df, KEY)
    assert q["columns"]["avg_price_eur"]["placeholders"] == {"*": 3}
    assert q["duplicate_keys"]["count"] == 1  # Beta appears twice in 2025
    assert q["rows_per_year"] == {"2024": 3, "2025": 3}


def test_rules(df):
    r = {x["rule"]["type"]: x for x in [
        facts.check_rule(df, {"type": "unique", "columns": KEY}),
        facts.check_rule(df, {"type": "numeric", "column": "avg_price_eur", "values": ["*"]}),
        facts.check_rule(df, {"type": "range", "column": "n_listings", "min": 30}),
        facts.check_rule(df, {"type": "ratio_range", "numerator": "avg_price_eur", "denominator": "avg_price_per_m2_eur",
                              "min": 20, "max": 300}),
    ]}
    assert r["unique"]["status"] == "fail" and r["unique"]["violations"] == 2
    assert r["numeric"]["status"] == "pass"  # "*" is allowed
    assert r["range"]["violations"] == 3
    assert r["ratio_range"]["status"] == "pass"  # 100 m² everywhere


def test_unknown_rule_and_missing_column_are_skipped_not_fatal(df):
    assert facts.check_rule(df, {"type": "regex", "column": "commune"})["status"] == "skipped"
    assert facts.check_rule(df, {"type": "not_null", "column": "nope"})["status"] == "skipped"


def test_toolbox(df):
    data = facts.analysis_frame(df, ["n_listings", "avg_price_eur", "avg_price_per_m2_eur"])
    tb = Toolbox(data, ["n_listings", "avg_price_eur", "avg_price_per_m2_eur"])
    g = json.loads(tb.run("growth", {"metric": "avg_price_eur", "start_year": 2024, "end_year": 2025, "n": 5}))
    assert g["communes_compared"] == 1 and g["highest"][0]["commune"] == "Alpha" and g["highest"][0]["pct_change"] == 20.0
    cov = json.loads(tb.run("coverage", {}))
    assert cov["by_year"][0]["avg_price_eur_present"] == 2
    assert all(s["strict"] and s["input_schema"]["additionalProperties"] is False for s in tb.specs)
    with pytest.raises(ValueError):
        tb.run("drop_table", {})


class FakeMessages:
    """Replays scripted responses: one tool call, then a final answer."""

    def __init__(self, responses):
        self.responses, self.requests = list(responses), []

    def create(self, **kw):
        self.requests.append(kw)
        return self.responses.pop(0)


def _resp(content, stop):
    r = SimpleNamespace(content=content, stop_reason=stop, model="fake", stop_details=None,
                        usage=SimpleNamespace(input_tokens=10, output_tokens=5))
    r._request_id = "req_test"
    return r


def test_agent_loop_runs_tools_and_returns_findings():
    tool_use = SimpleNamespace(type="tool_use", id="t1", name="coverage", input={})
    final = SimpleNamespace(type="text", text="- prices rose")
    msgs = FakeMessages([_resp([tool_use], "tool_use"), _resp([final], "end_turn")])
    c = Claude.__new__(Claude)
    c.client = SimpleNamespace(messages=msgs, beta=SimpleNamespace(messages=msgs))
    usage = Usage()
    text, calls = c.agent(model="claude-haiku-5-5", effort="low", system="s", user="u", tools=[],
                          run_tool=lambda n, a: '{"ok": true}', usage=usage)
    assert text == "- prices rose" and calls[0]["tool"] == "coverage" and usage.calls == 2
    assert msgs.requests[1]["messages"][-1]["content"][0]["tool_use_id"] == "t1"


def test_refusal_is_reported():
    c = Claude.__new__(Claude)
    with pytest.raises(LLMError):
        c._check(_resp([], "refusal"))
