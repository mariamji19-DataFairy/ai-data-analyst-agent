# Agentic Data Pipeline

A step-by-step data pipeline where **code computes the facts and an LLM (Claude) interprets them**. Each step is
isolated: it has its own prompt, model and settings, saves its own result, and can be inspected and re-run alone.

Demo dataset: **Luxembourg apartment asking prices by commune, 2010–2025** (Ministère du Logement, Observatoire de
l'Habitat, via [data.public.lu](https://data.public.lu/fr/datasets/prix-annonces-des-logements-par-commune/), CC0).

```
dataset.csv
   │
   ▼
[1 Profile] ─► [2 Quality] ─► [3 Integrity] ─► [4 Statistics agent] ─► [5 Summary]
 what is it?   what's wrong?   do the rules     which analyses        report for a manager
 + proposes                    hold?            matter? (tool use)    in English, French, Arabic
   validation rules ──────────────►┘
```

## Design: the LLM never does the arithmetic

LLMs are good at judgement and bad at exact numbers. So every step works in two halves:

| Step | Code computes (pandas) | Claude decides |
|---|---|---|
| 1 Profile | types, distinct values, numeric share, examples | what each column means; **proposes validation rules** (as data, from a fixed list of rule types) |
| 2 Quality | missing values, placeholders, duplicates, IQR outliers, similar spellings, rows per year | which findings are real problems, severity, the fix |
| 3 Integrity | runs every rule (from step 1 + `pipeline.yaml`) and counts violations | what each failure means; is the data safe to analyse, and on which conditions |
| 4 Statistics | a toolbox: `describe`, `trend`, `top_n`, `growth`, `correlation`, `coverage` | **an agent chooses which analyses to run** (tool use, max 8 calls), then writes findings citing tool results |
| 5 Summary | — | headline, findings, caveats, next steps, summaries in 3 languages |

Structured outputs guarantee every step's answer matches a JSON schema, and the statistics tools use strict schemas,
so a step can't return malformed results. Rules proposed by the model are executed by code from a whitelist
(`not_null`, `unique`, `numeric`, `range`, `allowed_values`, `ratio_range`): the model never runs code.

## You stay in control

- **One prompt file per step** in `prompts/`: edit it, re-run that step.
- **One config file**, `pipeline.yaml`: turn steps on/off, pick the model and effort per step, set the agent's tool budget.
- **Every result is saved** as JSON in `runs/<run>/`, with the facts, the model's answer, tokens used and request ids.
- **Review mode** stops after each step: continue, re-run (after editing the prompt), or stop.

## Run it

Requires [uv](https://docs.astral.sh/uv/) and a Claude API key from [console.anthropic.com](https://console.anthropic.com).

```bash
export ANTHROPIC_API_KEY=...            # once, e.g. in ~/.zshrc
uv sync
uv run adp extract                      # Excel workbook -> data/housing_apartments_2010_2025.csv
uv run adp run --dry-run                # every fact, no LLM calls (free)
uv run adp run --review                 # the full pipeline, pausing after each step
uv run adp run --step quality           # re-run one step in the last run
uv run adp show integrity               # print a step's result
```

The final report is written to `runs/<run>/report.md`. Routine steps run on Claude Haiku 5.5 and the agent and summary
on Claude Opus 5.5, so a full run costs a few cents; the cost table at the end of each report shows the exact tokens.

## What it found in the demo data (deterministic facts)

- 620 of 1,675 rows (37%) hide their prices as `*`: the publisher masks communes with fewer than 30 listings.
- The number of communes falls from 116 (2010) to 100 (2025) as communes merged, so commune-level trends need care.
- Some communes have 0 listings in a year.

## Project layout

```
pipeline.yaml        steps, models, effort, rules
prompts/             one prompt per step
src/adp/extract.py   workbook -> tidy CSV (keeps the published mess on purpose)
src/adp/facts.py     deterministic profiling, quality checks, rule engine
src/adp/tools.py     the statistics agent's toolbox (strict JSON schemas)
src/adp/llm.py       Claude calls: structured JSON, the tool-use loop, errors and refusals
src/adp/steps.py     the five steps
src/adp/pipeline.py  orchestration, saved results, review mode, report
tests/               offline tests (no API calls)
```

`uv run --group dev pytest` runs the tests.
