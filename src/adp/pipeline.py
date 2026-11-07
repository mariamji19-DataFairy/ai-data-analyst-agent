"""Runs the steps in order, saves each result, and (with --review) stops after each step for you to decide."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
import yaml

from .llm import Claude, LLMError, Usage
from .steps import STEPS, Ctx

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs"


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text())
    for s in cfg["steps"]:
        if s["id"] not in STEPS:
            raise ValueError(f"unknown step {s['id']!r} in {path.name} (known: {', '.join(STEPS)})")
    return cfg


def run_dir(run: str | None) -> Path:
    if run in (None, "new"):
        d = RUNS / datetime.now().strftime("%Y%m%d-%H%M%S")
        d.mkdir(parents=True, exist_ok=True)
        return d
    if run == "last":
        dirs = sorted(p for p in RUNS.glob("*") if p.is_dir())
        if not dirs:
            raise SystemExit("no earlier run: start one with `adp run`")
        return dirs[-1]
    d = RUNS / run
    if not d.is_dir():
        raise SystemExit(f"no run called {run!r} in {RUNS}")
    return d


def result_path(d: Path, index: int, step_id: str) -> Path:
    return d / f"{index}_{step_id}.json"


def load_previous(d: Path, steps: list[dict], upto: int) -> dict[str, dict]:
    out = {}
    for i, s in enumerate(steps[:upto], 1):
        p = result_path(d, i, s["id"])
        if p.exists():
            out[s["id"]] = json.loads(p.read_text())
    return out


def run(cfg: dict, *, only: list[str] | None, start: str | None, until: str | None, run_name: str | None,
        dry_run: bool, review: bool, log: Callable[[str], None] = print, ask: Callable[[str], str] = input) -> Path:
    steps = cfg["steps"]
    ids = [s["id"] for s in steps]
    lo = ids.index(start) if start else 0
    hi = ids.index(until) if until else len(ids) - 1
    selected = [s for i, s in enumerate(steps) if lo <= i <= hi and s.get("enabled", True) and (not only or s["id"] in only)]
    d = run_dir(run_name if run_name else ("last" if (only or start) else None))
    df = pd.read_csv(ROOT / cfg["dataset"], dtype=str, keep_default_na=False, na_values=[""])
    llm = None if dry_run else Claude()
    log(f"run {d.name} · dataset {cfg['dataset']} ({len(df)} rows){' · DRY RUN (no Claude calls)' if dry_run else ''}")

    i = 0
    while i < len(selected):
        s = selected[i]
        index = ids.index(s["id"]) + 1
        prompt = (ROOT / s["prompt"]).read_text()
        usage = Usage()
        ctx = Ctx(df=df, config=cfg, step=s, prompt=prompt, previous=load_previous(d, steps, index - 1),
                  llm=llm, usage=usage, log=lambda m: log(f"  {m}"))
        log(f"\n[{index}/{len(steps)}] {s['id']} · {s.get('model')} · effort {s.get('effort', 'medium')}")
        t0 = time.monotonic()
        try:
            res = STEPS[s["id"]](ctx)
        except LLMError as e:
            log(f"  ✗ {e}")
            raise SystemExit(1)
        res["meta"] = {"step": s["id"], "model": s.get("model"), "effort": s.get("effort"), "prompt": s["prompt"],
                       "seconds": round(time.monotonic() - t0, 1), "dry_run": dry_run, "usage": usage.as_dict(),
                       "finished_at": datetime.now().isoformat(timespec="seconds")}
        path = result_path(d, index, s["id"])
        path.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str))
        log(f"  ✓ saved {path.relative_to(ROOT)} · {usage.calls} call(s), {usage.input_tokens}+{usage.output_tokens} tokens")
        log(preview(s["id"], res))
        if review and not dry_run and i < len(selected) - 1:
            choice = ask("  [c]ontinue · [r]e-run this step (edit its prompt first) · [s]top ? ").strip().lower()[:1]
            if choice == "r":
                continue
            if choice == "s":
                log(f"stopped. Resume with: adp run --from {selected[i + 1]['id']} --run {d.name}")
                return d
        i += 1
    if (d / f"{len(steps)}_summary.json").exists():
        write_report(d, steps)
        log(f"\nreport: {(d / 'report.md').relative_to(ROOT)}")
    return d


def preview(step_id: str, res: dict) -> str:
    out = res.get("llm")
    if not out:
        return "  (no LLM output: dry run)"
    pick = {"profile": lambda o: f"{o['dataset_description']}\n  {len(o['proposed_rules'])} validation rules proposed",
            "quality": lambda o: f"quality: {o['overall_quality']} · {sum(x['is_real_problem'] for x in o['issues'])} real problem(s)\n  {o['summary']}",
            "integrity": lambda o: f"safe to analyse: {o['safe_to_analyse']}\n  {o['summary']}",
            "statistics": lambda o: o["findings_markdown"][:600] + ("…" if len(o["findings_markdown"]) > 600 else ""),
            "summary": lambda o: o["headline"]}
    try:
        return "  " + pick[step_id](out)
    except (KeyError, TypeError):
        return "  " + json.dumps(out, ensure_ascii=False)[:400]


def write_report(d: Path, steps: list[dict]) -> None:
    r = load_previous(d, steps, len(steps))
    lines = [f"# Data pipeline report · run {d.name}", ""]
    s = (r.get("summary") or {}).get("llm") or {}
    if s:
        lines += [f"## {s['headline']}", "", "### Key findings", *[f"- {x}" for x in s["key_findings"]], "",
                  "### Data caveats", *[f"- {x}" for x in s["data_caveats"]], "",
                  "### Next steps", *[f"- {x}" for x in s["next_steps"]], ""]
        for k, v in s.items():
            if k.startswith("summary_"):
                lines += [f"### Summary ({k.removeprefix('summary_')})", "", v, ""]
    q = (r.get("quality") or {}).get("llm") or {}
    if q:
        lines += ["## Data quality issues", "", "| Severity | Column | Issue | Real problem? | Fix |", "|---|---|---|---|---|"]
        lines += [f"| {i['severity']} | {i['column']} | {i['issue']} | {'yes' if i['is_real_problem'] else 'no'} | {i['recommended_fix']} |"
                  for i in q["issues"]]
        lines.append("")
    st = (r.get("statistics") or {}).get("llm") or {}
    if st:
        lines += ["## Statistics (agent findings)", "", st["findings_markdown"], ""]
    lines += ["## Cost", "", "| Step | Model | Calls | Input tokens | Output tokens |", "|---|---|---|---|---|"]
    for sid, res in r.items():
        u = res["meta"]["usage"]
        lines.append(f"| {sid} | {res['meta']['model']} | {u['calls']} | {u['input_tokens']} | {u['output_tokens']} |")
    (d / "report.md").write_text("\n".join(lines) + "\n")
