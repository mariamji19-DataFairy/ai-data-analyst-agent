"""adp: the command line.

  adp extract                       Excel workbook -> data/housing_apartments_2010_2025.csv
  adp steps                         list the steps and their settings
  adp run                           run every enabled step (a new run)
  adp run --review                  stop after each step: continue, re-run, or stop
  adp run --step quality            re-run one step in the last run (after editing its prompt)
  adp run --from integrity          continue the last run from a step
  adp run --dry-run                 compute every fact, call no LLM (free)
  adp show quality                  print a step's saved result from the last run
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .extract import extract_workbook
from .pipeline import ROOT, load_config, load_previous, run, run_dir


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="adp", description="Step-by-step, LLM-assisted data pipeline")
    p.add_argument("--config", default=str(ROOT / "pipeline.yaml"))
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="turn the raw workbook into the pipeline's CSV")
    e.add_argument("--xlsx", default=str(ROOT / "data/raw/vente-appartement-2010-2025.xlsx"))
    sub.add_parser("steps", help="list the steps")
    r = sub.add_parser("run", help="run the pipeline")
    r.add_argument("--step", action="append", help="run only this step (repeatable)")
    r.add_argument("--from", dest="start", help="start at this step")
    r.add_argument("--until", help="stop after this step")
    r.add_argument("--run", help="run folder to use: new | last | <name> (default: new, or last with --step/--from)")
    r.add_argument("--dry-run", action="store_true", help="compute facts only, no Claude calls")
    r.add_argument("--review", action="store_true", help="pause after each step")
    s = sub.add_parser("show", help="print a step's result")
    s.add_argument("step")
    s.add_argument("--run", default="last")
    s.add_argument("--facts", action="store_true", help="also print the computed facts")
    a = p.parse_args(argv)

    cfg = load_config(Path(a.config))
    if a.cmd == "extract":
        df = extract_workbook(Path(a.xlsx), ROOT / cfg["dataset"])
        print(f"wrote {cfg['dataset']}: {len(df)} rows, years {df['year'].min()}–{df['year'].max()}")
    elif a.cmd == "steps":
        for i, st in enumerate(cfg["steps"], 1):
            on = "on " if st.get("enabled", True) else "off"
            print(f"{i}. {st['id']:<11} {on}  {st.get('model', '-'):<18} effort {st.get('effort', 'medium'):<7} {st['prompt']}")
    elif a.cmd == "run":
        run(cfg, only=a.step, start=a.start, until=a.until, run_name=a.run, dry_run=a.dry_run, review=a.review)
    elif a.cmd == "show":
        d = run_dir(a.run)
        res = load_previous(d, cfg["steps"], len(cfg["steps"])).get(a.step)
        if not res:
            raise SystemExit(f"no result for {a.step!r} in run {d.name}")
        out = res if a.facts else {"llm": res.get("llm"), "meta": res.get("meta")}
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
