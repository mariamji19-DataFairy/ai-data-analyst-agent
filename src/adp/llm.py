"""Calls to Claude: one structured-JSON call per step, plus a tool-use loop for the statistics agent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

import anthropic

# Models with server-side refusal fallbacks (re-runs a declined request on another model in the same call).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5", "claude-fable-5-1"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    log: list[dict] = field(default_factory=list)

    def add(self, response) -> None:
        self.calls += 1
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        self.log.append({"model": response.model, "stop_reason": response.stop_reason,
                         "input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens,
                         "request_id": response._request_id})

    def as_dict(self) -> dict:
        return {"calls": self.calls, "input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "log": self.log}


class LLMError(RuntimeError):
    pass


def load_dotenv(path) -> None:
    """KEY=value lines from a local .env (gitignored) into the environment, without overriding what's already set."""
    import os
    from pathlib import Path
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Claude:
    def __init__(self) -> None:
        from pathlib import Path
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY (or an `ant auth login` profile)

    def _create(self, model: str, **kw):
        try:
            if model in FALLBACK_MODELS:
                return self.client.beta.messages.create(model=model, betas=[FALLBACK_BETA], fallbacks="default", **kw)
            return self.client.messages.create(model=model, **kw)
        except anthropic.AuthenticationError as e:
            raise LLMError("Claude API key missing or invalid: set ANTHROPIC_API_KEY (see README)") from e
        except anthropic.RateLimitError as e:
            raise LLMError("rate limited by the Claude API: wait a minute and re-run this step") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("could not reach the Claude API: check the internet connection") from e

    @staticmethod
    def _check(response) -> None:
        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            raise LLMError(f"the model declined this step ({getattr(detail, 'category', None) or 'no category'})")
        if response.stop_reason == "max_tokens":
            raise LLMError("the answer was cut off (max_tokens): raise max_tokens for this step in pipeline.yaml")

    def ask_json(self, *, model: str, effort: str, system: str, user: str, schema: dict, usage: Usage,
                 max_tokens: int = 16000) -> dict:
        """One call whose answer is guaranteed to match `schema` (structured outputs)."""
        r = self._create(model, max_tokens=max_tokens, system=system,
                         output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                         messages=[{"role": "user", "content": user}])
        usage.add(r)
        self._check(r)
        text = next(b.text for b in r.content if b.type == "text")
        return json.loads(text)

    def agent(self, *, model: str, effort: str, system: str, user: str, tools: list[dict],
              run_tool: Callable[[str, dict], str], usage: Usage, max_tool_calls: int = 8,
              max_tokens: int = 16000, on_tool: Callable[[str, dict], None] | None = None) -> tuple[str, list[dict]]:
        """A plain tool-use loop: Claude picks tools, the code runs them, until Claude answers or the budget runs out.
        Returns (final text, every tool call with its result)."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        calls: list[dict] = []
        refused_rounds = 0
        while True:
            budget_left = max_tool_calls - len(calls)
            if budget_left <= 0:
                refused_rounds += 1
                if refused_rounds > 2:  # it keeps asking for tools after the budget: stop rather than loop
                    raise LLMError(f"the agent kept calling tools after its budget of {max_tool_calls}")
            r = self._create(model, max_tokens=max_tokens, system=system, tools=tools,
                             output_config={"effort": effort}, messages=messages)
            usage.add(r)
            self._check(r)
            uses = [b for b in r.content if b.type == "tool_use"]
            if r.stop_reason != "tool_use" or not uses:
                return "\n".join(b.text for b in r.content if b.type == "text").strip(), calls
            messages.append({"role": "assistant", "content": r.content})
            results = []
            for b in uses:
                if budget_left <= 0:
                    results.append({"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                                    "content": "Tool budget used up. Write your findings now from the results you have."})
                    continue
                budget_left -= 1
                if on_tool:
                    on_tool(b.name, b.input)
                try:
                    out, err = run_tool(b.name, b.input), False
                except Exception as e:  # a bad argument is reported back to the model, not fatal
                    out, err = f"Error: {e}", True
                calls.append({"tool": b.name, "input": b.input, "result": out, "error": err})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": out, "is_error": err})
            messages.append({"role": "user", "content": results})
