"""Turn the Observatoire de l'Habitat workbook (one sheet per year) into one tidy CSV.

Deliberately light-touch: values are kept as published (prices hidden as "*" stay "*"),
so the pipeline's quality and integrity steps have the real-world mess to find.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLUMNS = ["year", "commune", "n_listings", "avg_price_eur", "avg_price_per_m2_eur"]


def extract_workbook(xlsx: Path, out_csv: Path) -> pd.DataFrame:
    book = pd.ExcelFile(xlsx)
    frames = []
    for sheet in book.sheet_names:
        raw = pd.read_excel(book, sheet_name=sheet, header=None, dtype=object)
        header = raw.index[raw[2].astype(str).str.strip().eq("Commune")]
        if header.empty:
            continue
        rows = []
        for _, r in raw.iloc[header[0] + 1:].iterrows():
            commune = r[2]
            if pd.isna(commune) or not str(commune).strip():
                break  # the table ends at the first blank row (notes and totals follow)
            rows.append([sheet, commune, r[3], r[4], r[5]])
        frames.append(pd.DataFrame(rows, columns=COLUMNS))
    df = pd.concat(frames, ignore_index=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    return df
