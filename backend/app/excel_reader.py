from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pandas as pd
from fastapi import HTTPException


NAME_CANDIDATES = ["NAMA", "NAMA MAHASISWA", "NAMA LENGKAP", "NAME"]
CLASS_CANDIDATES = ["KODE KELAS PAI", "KELAS PAI", "KODE KELAS", "KELAS"]


@dataclass
class ExcelData:
    df: pd.DataFrame
    sheets: list[dict[str, Any]]
    name_col: str | None
    class_col: str | None


def clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).replace("\u00a0", " ").strip() for c in df.columns]
    return df


def find_column(columns, candidates: list[str]) -> str | None:
    lookup = {str(c).strip().upper(): c for c in columns}
    for c in candidates:
        if c in lookup:
            return lookup[c]
    for col in columns:
        up = str(col).strip().upper()
        for candidate in candidates:
            if candidate in up:
                return col
    return None


def read_rekap_excel(contents: bytes) -> ExcelData:
    try:
        xls = pd.ExcelFile(BytesIO(contents), engine="openpyxl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"File rekap tidak bisa dibaca sebagai Excel: {exc}") from exc

    frames: list[pd.DataFrame] = []
    sheets: list[dict[str, Any]] = []
    row_id = 1

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, dtype=object)
        df = clean_columns(df)
        df = df.dropna(how="all")
        if df.empty:
            continue

        df["_sheet_asal_rekap"] = sheet_name
        ids = []
        for _ in range(len(df)):
            ids.append(f"r{row_id}")
            row_id += 1
        df["_row_id"] = ids

        frames.append(df)
        sheets.append({
            "sheet": sheet_name,
            "rows": int(len(df)),
            "columns": [str(c) for c in df.columns if not str(c).startswith("_")]
        })

    if not frames:
        raise HTTPException(status_code=400, detail="File rekap tidak berisi data.")

    combined = pd.concat(frames, ignore_index=True, sort=False)
    name_col = find_column(combined.columns, NAME_CANDIDATES)
    class_col = find_column(combined.columns, CLASS_CANDIDATES)

    if not name_col:
        raise HTTPException(
            status_code=400,
            detail={"message": "Kolom nama mahasiswa tidak ditemukan di rekap.", "columns": list(map(str, combined.columns))}
        )

    return ExcelData(df=combined, sheets=sheets, name_col=name_col, class_col=class_col)


def read_master_excel(contents: bytes) -> ExcelData:
    try:
        df = pd.read_excel(BytesIO(contents), dtype=object, engine="openpyxl")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"File master tidak bisa dibaca sebagai Excel: {exc}") from exc

    df = clean_columns(df).dropna(how="all")
    name_col = find_column(df.columns, NAME_CANDIDATES)
    class_col = find_column(df.columns, CLASS_CANDIDATES)

    missing = []
    if not name_col:
        missing.append("NAMA")
    if not class_col:
        missing.append("KODE KELAS PAI")
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"message": f"Kolom wajib master tidak ditemukan: {', '.join(missing)}", "columns": list(map(str, df.columns))}
        )

    return ExcelData(
        df=df,
        sheets=[{"sheet": "MASTER", "rows": int(len(df)), "columns": list(map(str, df.columns))}],
        name_col=name_col,
        class_col=class_col,
    )
