# Agentic Data Pipeline: handover
_Last updated: 2026-11-07 (by Claude, session summary)_

## Current status
Built and tested offline (6 tests pass, dry run works). **No real Claude run yet**: no API key on this machine.
Portfolio project for Mariam's job search (backs the "AI Enthusiast" line on her CV) and PhD applications (data-to-text).

## Decisions (dated)
- 2026-11-07: Claude API (her choice), Haiku 5.5 for profile/quality/integrity, Opus 5.5 for the statistics agent and
  summary (she picked the "cheap Haiku for most steps" option). Refusal fallbacks on for Opus.
- 2026-11-07: Code computes all numbers; the LLM judges. Model-proposed rules run from a whitelist, never as code.
- 2026-11-07: Dataset: Observatoire de l'Habitat apartment asking prices 2010–2025 (CC0), kept with its real mess.
- 2026-11-07: API key lives in a local `.env` (gitignored), read by `llm.load_dotenv`; never commit it.
- 2026-11-07: Manual tool-use loop (not the beta tool runner) so every call is visible and easy to explain.

## Completed recently
- extract, facts, tools, llm, steps, pipeline, cli; config + 5 prompts; README; tests.

## Blockers / waiting on the owner
- ANTHROPIC_API_KEY: Mariam will paste it; save it to `.env` (KEY=value), not to git or docs.
- Decide whether to publish on GitHub (public repo = portfolio link).

## Next steps (ordered)
1. Key → `uv run adp run --review`; read each step, tune prompts.
2. Check structured-output schemas against the live API (nullable unions in RULE).
3. Commit a sample report (copy one runs/<run>/report.md to docs/sample_report.md) for the README.
4. Optional: a small chart of the national trend for the README; publish on GitHub; LinkedIn post.

## How to run / verify
- `uv run adp run --dry-run` (free) · `uv run adp run --review` · `uv run --group dev pytest`

## Session log
- 2026-11-07: Project created end to end; offline tests pass; waiting for an API key.
- 2026-11-07: Added `.env` loading for the API key (6 tests pass).

<!-- AUTO-STATUS:START (maintained by ~/.claude/hooks/local_handoff.py, do not edit by hand) -->
## Auto status
- Branch: `main`
- Last commit: 4a705cd Agentic data pipeline: profile, quality, integrity, statistics agent, summary (2026-11-07)
- Uncommitted files: 1:
  - `src/adp/llm.py`
<!-- AUTO-STATUS:END -->
