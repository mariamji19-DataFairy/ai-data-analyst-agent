"""The five steps. Each one: (1) code computes facts, (2) Claude reads them with the step's prompt, (3) a JSON result.

A step only reads the dataset and the saved results of earlier steps, so any step can be re-run on its own.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from . import facts
from .llm import Claude, Usage
from .tools import Toolbox


@dataclass
class Ctx:
    df: pd.DataFrame
    config: dict
    step: dict  # this step's settings from pipeline.yaml
    prompt: str  # this step's prompt file
    previous: dict[str, dict]  # results of earlier steps, by step id
    llm: Claude | None  # None = dry run: compute facts, skip Claude
    usage: Usage
    log: Callable[[str], None]


def _user(facts_obj: Any, extra: str = "") -> str:
    return (extra + "\n\n" if extra else "") + "FACTS (computed by code, exact):\n```json\n" + \
        json.dumps(facts_obj, ensure_ascii=False, indent=1, default=str) + "\n```"


def _ask(ctx: Ctx, facts_obj: Any, schema: dict, extra: str = "") -> dict | None:
    if ctx.llm is None:
        return None
    return ctx.llm.ask_json(model=ctx.step["model"], effort=ctx.step.get("effort", "medium"), system=ctx.prompt,
                            user=_user(facts_obj, extra), schema=schema, usage=ctx.usage,
                            max_tokens=ctx.step.get("max_tokens", 16000))


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


STR, NUM_OR_NULL, STR_OR_NULL = {"type": "string"}, {"type": ["number", "null"]}, {"type": ["string", "null"]}
STRS = {"type": "array", "items": STR}
SEVERITY = {"type": "string", "enum": ["high", "medium", "low"]}

RULE = _obj({"type": {"type": "string", "enum": facts.RULE_TYPES}, "column": STR_OR_NULL,
             "columns": {"type": ["array", "null"], "items": STR}, "min": NUM_OR_NULL, "max": NUM_OR_NULL,
             "values": {"type": ["array", "null"], "items": STR}, "numerator": STR_OR_NULL,
             "denominator": STR_OR_NULL, "reason": STR})


# --------------------------------------------------------------------------- 1 profile

def profile(ctx: Ctx) -> dict:
    f = facts.profile(ctx.df)
    ctx.log(f"{f['rows']} rows × {f['columns']} columns")
    schema = _obj({
        "dataset_description": STR,
        "columns": {"type": "array", "items": _obj({"column": STR, "meaning": STR, "expected_type": STR, "notes": STR})},
        "proposed_rules": {"type": "array", "items": RULE},
        "questions_for_owner": STRS,
    })
    return {"facts": f, "llm": _ask(ctx, f, schema, f"Dataset key: {ctx.config['key']}")}


# --------------------------------------------------------------------------- 2 quality

def quality(ctx: Ctx) -> dict:
    f = facts.quality(ctx.df, ctx.config["key"])
    ctx.log(f"{f['duplicate_rows']} duplicate rows, {f['duplicate_keys']['count']} duplicate keys")
    meaning = ((ctx.previous.get("profile") or {}).get("llm") or {}).get("columns")
    schema = _obj({
        "issues": {"type": "array", "items": _obj({"column": STR, "issue": STR, "evidence": STR, "severity": SEVERITY,
                                                     "is_real_problem": {"type": "boolean"}, "recommended_fix": STR})},
        "overall_quality": {"type": "string", "enum": ["good", "acceptable", "poor"]},
        "summary": STR,
    })
    extra = "Column meanings from the profile step:\n" + json.dumps(meaning, ensure_ascii=False) if meaning else ""
    return {"facts": f, "llm": _ask(ctx, f, schema, extra)}


# --------------------------------------------------------------------------- 3 integrity

def integrity(ctx: Ctx) -> dict:
    proposed = ((ctx.previous.get("profile") or {}).get("llm") or {}).get("proposed_rules")
    rules = (ctx.config.get("extra_rules") or []) + (proposed or facts.default_rules(ctx.config["key"]))
    results = [facts.check_rule(ctx.df, r) for r in rules]
    f = {"rules_checked": len(results), "failed": sum(r["status"] == "fail" for r in results),
         "skipped": sum(r["status"] == "skipped" for r in results), "results": results}
    ctx.log(f"{f['rules_checked']} rules: {f['failed']} failed, {f['skipped']} skipped")
    quality_issues = ((ctx.previous.get("quality") or {}).get("llm") or {}).get("issues")
    schema = _obj({
        "verdicts": {"type": "array", "items": _obj({"rule": STR, "status": STR, "interpretation": STR,
                                                       "severity": SEVERITY, "action": STR})},
        "safe_to_analyse": {"type": "boolean"},
        "conditions_for_analysis": STRS,
        "summary": STR,
    })
    extra = "Issues found by the quality step:\n" + json.dumps(quality_issues, ensure_ascii=False) if quality_issues else ""
    return {"facts": f, "llm": _ask(ctx, f, schema, extra)}


# --------------------------------------------------------------------------- 4 statistics (agent)

def statistics(ctx: Ctx) -> dict:
    metrics = ctx.config["metrics"]
    data = facts.analysis_frame(ctx.df, metrics)
    tb = Toolbox(data, metrics, ctx.config.get("group_column", "commune"), ctx.config.get("time_column", "year"))
    if ctx.llm is None:
        return {"facts": {"coverage": tb.coverage(), "tools": [t["name"] for t in tb.specs]}, "llm": None}
    integ = (ctx.previous.get("integrity") or {}).get("llm") or {}
    brief = {"metrics": metrics, "years": sorted(int(y) for y in data[tb.time].dropna().unique()),
             "conditions_for_analysis": integ.get("conditions_for_analysis"),
             "integrity_summary": integ.get("summary")}
    text, calls = ctx.llm.agent(
        model=ctx.step["model"], effort=ctx.step.get("effort", "medium"), system=ctx.prompt,
        user=_user(brief, "Analyse this dataset with your tools."), tools=tb.specs, run_tool=tb.run,
        usage=ctx.usage, max_tool_calls=ctx.step.get("max_tool_calls", 8), max_tokens=ctx.step.get("max_tokens", 16000),
        on_tool=lambda name, args: ctx.log(f"  agent → {name}({json.dumps(args, ensure_ascii=False)})"))
    return {"facts": {"tool_calls": calls}, "llm": {"findings_markdown": text}}


# --------------------------------------------------------------------------- 5 summary

def summary(ctx: Ctx) -> dict:
    langs = ctx.step.get("languages", ["en"])
    prior = {sid: (res or {}).get("llm") for sid, res in ctx.previous.items()}
    props: dict[str, Any] = {"headline": STR, "key_findings": STRS, "data_caveats": STRS, "next_steps": STRS}
    for lang in langs:
        props[f"summary_{lang}"] = STR
    out = _ask(ctx, prior, _obj(props), f"Write the summaries in these languages: {', '.join(langs)}.")
    return {"facts": {"languages": langs, "steps_used": list(prior)}, "llm": out}


STEPS: dict[str, Callable[[Ctx], dict]] = {
    "profile": profile, "quality": quality, "integrity": integrity, "statistics": statistics, "summary": summary}
