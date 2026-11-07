"""The statistics step's toolbox. The agent decides WHICH analyses to run; the code runs them.

Each tool: a JSON schema the model sees (strict, so arguments always validate) and a pandas implementation.
Results are small JSON objects, so the agent's numbers always come from here.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import pandas as pd

from .facts import _py


def _schema(props: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


class Toolbox:
    def __init__(self, df: pd.DataFrame, metrics: list[str], group_col: str = "commune", time_col: str = "year"):
        self.df, self.metrics, self.group, self.time = df, metrics, group_col, time_col
        metric = {"type": "string", "enum": metrics}
        self.specs: list[dict] = [
            {"name": "describe", "description": "Count, mean, median, min, max and quartiles of a metric, for one year or all years.",
             "input_schema": _schema({"metric": metric, "year": {"type": ["integer", "null"]}}, ["metric", "year"])},
            {"name": "trend", "description": f"Yearly mean and median of a metric, nationally or for one {group_col}.",
             "input_schema": _schema({"metric": metric, "commune": {"type": ["string", "null"]}}, ["metric", "commune"])},
            {"name": "top_n", "description": f"The n {group_col}s with the highest (or lowest) value of a metric in a year.",
             "input_schema": _schema({"metric": metric, "year": {"type": "integer"}, "n": {"type": "integer"},
                                      "lowest": {"type": "boolean"}}, ["metric", "year", "n", "lowest"])},
            {"name": "growth", "description": f"{group_col}s with the largest % change of a metric between two years (both values present).",
             "input_schema": _schema({"metric": metric, "start_year": {"type": "integer"}, "end_year": {"type": "integer"},
                                      "n": {"type": "integer"}}, ["metric", "start_year", "end_year", "n"])},
            {"name": "correlation", "description": "Pearson correlation between two metrics, for one year or all years.",
             "input_schema": _schema({"metric_a": metric, "metric_b": metric, "year": {"type": ["integer", "null"]}},
                                     ["metric_a", "metric_b", "year"])},
            {"name": "coverage", "description": f"Per year: rows, and how many {group_col}s have each metric present (not hidden).",
             "input_schema": _schema({}, [])},
        ]
        for s in self.specs:
            s["strict"] = True
        self.impl: dict[str, Callable[..., Any]] = {
            "describe": self.describe, "trend": self.trend, "top_n": self.top_n,
            "growth": self.growth, "correlation": self.correlation, "coverage": self.coverage}

    def run(self, name: str, args: dict) -> str:
        if name not in self.impl:
            raise ValueError(f"unknown tool {name!r}")
        return json.dumps(self.impl[name](**args), ensure_ascii=False, default=str)

    def _year(self, year):
        return self.df if year is None else self.df[self.df[self.time] == year]

    def describe(self, metric, year):
        d = self._year(year)[metric].describe()
        return {"metric": metric, "year": year, **{k: _py(v) for k, v in d.items()}, "median": _py(self._year(year)[metric].median())}

    def trend(self, metric, commune):
        d = self.df if commune is None else self.df[self.df[self.group] == commune]
        if d.empty:
            return {"error": f"no rows for {self.group} {commune!r}"}
        g = d.groupby(self.time)[metric].agg(["mean", "median", "count"])
        return {"metric": metric, "commune": commune,
                "by_year": [{"year": int(y), **{k: _py(v) for k, v in r.items()}} for y, r in g.iterrows()]}

    def top_n(self, metric, year, n, lowest):
        d = self._year(year).dropna(subset=[metric]).sort_values(metric, ascending=lowest).head(max(1, min(n, 20)))
        return {"metric": metric, "year": year, "lowest": lowest,
                "rows": [{self.group: r[self.group], metric: _py(r[metric])} for _, r in d.iterrows()]}

    def growth(self, metric, start_year, end_year, n):
        # one value per commune and year (averaged if a duplicate key slipped through)
        a = self._year(start_year).groupby(self.group)[metric].mean()
        b = self._year(end_year).groupby(self.group)[metric].mean()
        both = pd.concat([a, b], axis=1, keys=["start", "end"]).dropna()
        both = both[both["start"] > 0]
        both["pct_change"] = (both["end"] / both["start"] - 1) * 100
        both = both.sort_values("pct_change", ascending=False)
        n = max(1, min(n, 20))
        fmt = lambda part: [{self.group: i, "start": _py(r["start"]), "end": _py(r["end"]), "pct_change": _py(r["pct_change"])}
                            for i, r in part.iterrows()]
        return {"metric": metric, "start_year": start_year, "end_year": end_year, "communes_compared": int(len(both)),
                "median_pct_change": _py(both["pct_change"].median()), "highest": fmt(both.head(n)), "lowest": fmt(both.tail(n))}

    def correlation(self, metric_a, metric_b, year):
        d = self._year(year)[[metric_a, metric_b]].dropna()
        return {"metric_a": metric_a, "metric_b": metric_b, "year": year, "n": int(len(d)),
                "pearson_r": _py(d[metric_a].corr(d[metric_b])) if len(d) > 2 else None}

    def coverage(self):
        g = self.df.groupby(self.time)
        return {"by_year": [{"year": int(y), "rows": int(len(part)), **{f"{m}_present": int(part[m].notna().sum()) for m in self.metrics}}
                            for y, part in g]}
