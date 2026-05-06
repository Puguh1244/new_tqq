from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pandas as pd

from app.excel_reader import ExcelData
from app.matching import normalize_class
from app.schemas import AnalysisResult


AUDIT_TECH_COLS = {
    "SHEET ASAL REKAP", "NAMA MASTER", "STATUS MAPPING", "CONFIDENCE", "CATATAN",
    "_sheet_asal_rekap", "_row_id", "nama_rekap_normalized", "nama_master_normalized",
}

SOURCE_NUMBER_HEADERS = {"NO", "NOMOR", "NOURUT", "NOMORURUT", "NUMBER", "NUM"}
FORMULA_PREFIXES = ("=", "+", "-", "@")
FORMULA_CONTROL_PREFIXES = ("\t", "\r", "\n")


def normalize_header(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").strip().upper())


def is_source_number_column(column: Any) -> bool:
    """Detect source row-number columns such as NO, No., Nomor, Nomor Urut.

    These columns come from the uploaded Excel and must not be carried into
    generated class sheets because the app creates a fresh NO column per class.
    """
    return normalize_header(column) in SOURCE_NUMBER_HEADERS


def drop_source_number_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in df.columns if is_source_number_column(c)]
    return df.drop(columns=cols, errors="ignore")


def escape_formula_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith(FORMULA_CONTROL_PREFIXES) or value.lstrip().startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def sanitize_df_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    return df.map(escape_formula_value)


def write_excel_df(writer: pd.ExcelWriter, df: pd.DataFrame, sheet_name: str) -> None:
    sanitize_df_for_excel(df).to_excel(writer, sheet_name=sheet_name, index=False)


def sanitize_sheet_name(name: Any) -> str:
    text = str(name or "TANPA_KELAS").strip() or "TANPA_KELAS"
    text = re.sub(r"[\\/*?:\[\]]", "-", text)
    return text[:31]


def clean_class_df(df: pd.DataFrame, final_class: str, class_col: str | None) -> pd.DataFrame:
    out = df.copy()
    drop_cols = [
        c for c in out.columns
        if str(c).startswith("_") or str(c).upper() in AUDIT_TECH_COLS or is_source_number_column(c)
    ]
    out = out.drop(columns=drop_cols, errors="ignore")

    if class_col and class_col in out.columns:
        out[class_col] = final_class
    else:
        out["KODE KELAS PAI"] = final_class

    out.insert(0, "NO", range(1, len(out) + 1))
    return out


def df_from_records(records: list[dict[str, Any]], empty_columns: list[str]) -> pd.DataFrame:
    if records:
        return pd.DataFrame(records)
    return pd.DataFrame(columns=empty_columns)


def generate_excel_file(out_path: Path, mode: str, rekap: ExcelData, result: AnalysisResult) -> None:
    mapping_by_row = {m.get("row_id"): m for m in result.mapping}
    grouped: dict[str, list[dict[str, Any]]] = {}
    unmapped_rows: list[dict[str, Any]] = []

    for _, row in rekap.df.iterrows():
        # Keep the uploaded source data, but remove its original row-number column
        # (NO, No., Nomor, etc.). A fresh NO is created later per class sheet.
        row_dict = {k: v for k, v in row.to_dict().items() if not is_source_number_column(k)}
        m = mapping_by_row.get(row.get("_row_id"), {})
        if mode == "without_master":
            final_class = normalize_class(row.get(rekap.class_col)) if rekap.class_col else ""
            ok = bool(final_class)
        else:
            final_class = normalize_class(m.get("kode_kelas_pai"))
            ok = m.get("status_mapping") in {"EXACT_MATCH", "NORMALIZED_MATCH", "FUZZY_HIGH_CONFIDENCE", "APPROVED_BY_USER"} and bool(final_class)

        if ok:
            grouped.setdefault(final_class, []).append(row_dict)
        else:
            row_dict.update({
                "STATUS MAPPING": m.get("status_mapping", "UNMAPPED"),
                "NAMA MASTER": m.get("nama_master", ""),
                "CONFIDENCE": m.get("confidence", 0),
                "CATATAN": m.get("catatan", ""),
            })
            unmapped_rows.append(row_dict)

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        used = set()
        for klass, rows in sorted(grouped.items()):
            sheet_name = sanitize_sheet_name(klass)
            base = sheet_name
            i = 2
            while sheet_name in used:
                suffix = f"_{i}"
                sheet_name = f"{base[:31-len(suffix)]}{suffix}"
                i += 1
            used.add(sheet_name)
            class_df = clean_class_df(pd.DataFrame(rows), klass, rekap.class_col)
            write_excel_df(writer, class_df, sheet_name)

        write_excel_df(writer, df_from_records(result.mapping, ["mapping_id", "nama_rekap", "nama_master", "kode_kelas_pai", "status_mapping"]), "LOG_MAPPING")
        write_excel_df(writer, df_from_records([x for x in result.mapping if x.get("status_mapping") == "NEEDS_CONFIRMATION"], ["mapping_id", "nama_rekap", "nama_master", "kode_kelas_pai", "confidence"]), "PERLU_KONFIRMASI")
        write_excel_df(writer, pd.DataFrame(unmapped_rows), "BELUM_TERPETAKAN")
        write_excel_df(writer, df_from_records(result.duplicates, ["source", "nama", "nama_normalized", "count"]), "NAMA_DUPLIKAT")
        write_excel_df(writer, df_from_records(result.missing_scores, ["row_id", "sheet_asal", "nama", "catatan"]), "BELUM_ADA_NILAI")
        write_excel_df(writer, df_from_records(result.validation_scores, ["row_id", "sheet_asal", "nama", "kolom_nilai", "nilai", "jenis_masalah", "catatan"]), "VALIDASI_NILAI")
        write_excel_df(writer, df_from_records(result.validation_codes, ["row_id", "sheet_asal", "nama", "kode_kelas_pai", "jenis_masalah", "catatan"]), "VALIDASI_KODE")
        write_excel_df(writer, pd.DataFrame([result.summary]), "RINGKASAN")
