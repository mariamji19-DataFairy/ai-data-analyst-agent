# Agentic Data Pipeline: handover
_Last updated: 2026-11-07 (by Claude, session summary)_

## Current status
First full run done 2026-11-07 (run 20261107-211726, $0.15, sample in docs/sample_report.md). API key in local `.env`.
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
- Decide whether to publish on GitHub (public repo = portfolio link).

## Next steps (ordered)
1. Prompt tuning: the summary added 'northern rural' (not in the data); statistics should run the spelling check or say it's out of scope.
2. Optional: a 'clean' step that writes the cleaned CSV following the integrity conditions.
4. Optional: a small chart of the national trend for the README; publish on GitHub; LinkedIn post.

## How to run / verify
- `uv run adp run --dry-run` (free) · `uv run adp run --review` · `uv run --group dev pytest`

## Session log
- 2026-11-07: Project created end to end; offline tests pass; waiting for an API key.
- 2026-11-07: Added `.env` loading for the API key (6 tests pass).
- 2026-11-07: First real run OK ($0.15). Fixes: `.venv` moved to `.venv.nosync` (iCloud on Desktop broke it); spelling check always reported.

<!-- AUTO-STATUS:START (maintained by ~/.claude/hooks/local_handoff.py, do not edit by hand) -->
## Auto status
- Branch: `main`
- Last commit: e8b46b8 Read the API key from a local .env file (2026-11-07)
- Uncommitted files: 0
<!-- AUTO-STATUS:END -->
