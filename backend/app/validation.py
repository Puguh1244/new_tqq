from __future__ import annotations

import re
from typing import Any

import pandas as pd

CLASS_PATTERN = re.compile(r"^AI\d{3}$", re.IGNORECASE)
SCORE_KEYWORDS = ["NILAI", "TOTAL", "PRESENSI", "BACAAN", "HAFALAN", "EVALUASI", "TUGAS", "UJIAN"]
NON_SCORE = ["NO", "NIM", "NPM", "NAMA", "KODE", "KELAS", "HP", "TELP", "WA"]


def to_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("\u00a0", " ").strip()
    text = re.sub(r"[^0-9,\.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    elif "," in text and "." in text:
        text = text.replace(",", "")
    try:
        return float(text)
    except Exception:
        return None


def is_score_column(col: str) -> bool:
    up = str(col).strip().upper()
    if up.startswith("_"):
        return False
    if any(x == up or x in up for x in NON_SCORE):
        return False
    return any(k in up for k in SCORE_KEYWORDS)


def detect_score_columns(df: pd.DataFrame) -> list[str]:
    cols = [c for c in df.columns if is_score_column(str(c))]
    return list(dict.fromkeys(cols))


def validate_scores(df: pd.DataFrame, name_col: str | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    score_cols = detect_score_columns(df)

    for _, row in df.iterrows():
        nama = str(row.get(name_col, "")) if name_col else ""
        all_blank = True
        numeric_values: dict[str, float] = {}

        for col in score_cols:
            value = row.get(col)
            number = to_float(value)
            if number is not None:
                all_blank = False
                numeric_values[str(col).upper()] = number

            base = {
                "row_id": row.get("_row_id"),
                "sheet_asal": row.get("_sheet_asal_rekap"),
                "nama": nama,
                "kolom_nilai": str(col),
                "nilai": None if value is None or pd.isna(value) else str(value),
            }

            if value is None or pd.isna(value) or str(value).strip() == "":
                issues.append({**base, "jenis_masalah": "NILAI_KOSONG", "catatan": "Nilai kosong."})
                continue
            if number is None:
                issues.append({**base, "jenis_masalah": "FORMAT_TIDAK_NUMERIK", "catatan": "Nilai tidak bisa dibaca sebagai angka."})
                continue
            if number > 100:
                issue_type = "NILAI_LEBIH_DARI_100"
                note = "Nilai lebih dari 100."
                if "TOTAL" in str(col).upper() and number >= 1000:
                    issue_type = "TOTAL_NILAI_MENCURIGAKAN"
                    note = "Total nilai sangat besar; kemungkinan desimal atau pemisah ribuan salah."
                issues.append({**base, "jenis_masalah": issue_type, "catatan": note})
            if number < 0:
                issues.append({**base, "jenis_masalah": "NILAI_KURANG_DARI_0", "catatan": "Nilai kurang dari 0."})

        if score_cols and all_blank:
            missing_rows.append({
                "row_id": row.get("_row_id"),
                "sheet_asal": row.get("_sheet_asal_rekap"),
                "nama": nama,
                "catatan": "Semua kolom nilai kosong.",
            })

        total_keys = [k for k in numeric_values if "TOTAL" in k]
        comp_keys = [k for k in numeric_values if any(x in k for x in ["PRESENSI", "BACAAN", "HAFALAN", "EVALUASI"])]
        if total_keys and len(comp_keys) >= 4:
            comp_avg = sum(numeric_values[k] for k in comp_keys) / len(comp_keys)
            total_val = numeric_values[total_keys[0]]
            if abs(total_val - comp_avg) > 1.0:
                issues.append({
                    "row_id": row.get("_row_id"),
                    "sheet_asal": row.get("_sheet_asal_rekap"),
                    "nama": nama,
                    "kolom_nilai": total_keys[0],
                    "nilai": str(total_val),
                    "jenis_masalah": "TOTAL_TIDAK_SESUAI_RATA_RATA",
                    "catatan": f"Total berbeda dari rata-rata komponen ({comp_avg:.2f}).",
                })

    return issues, missing_rows


def validate_class_codes(df: pd.DataFrame, class_col: str | None, name_col: str | None = None) -> list[dict[str, Any]]:
    if not class_col or class_col not in df.columns:
        return [{"jenis_masalah": "KOLOM_KODE_KELAS_TIDAK_ADA", "catatan": "Kolom KODE KELAS PAI tidak ditemukan."}]

    out: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        raw = row.get(class_col)
        code = "" if raw is None or pd.isna(raw) else str(raw).strip().upper()
        if not code:
            out.append({
                "row_id": row.get("_row_id"),
                "sheet_asal": row.get("_sheet_asal_rekap"),
                "nama": str(row.get(name_col, "")) if name_col else "",
                "kode_kelas_pai": code,
                "jenis_masalah": "KODE_KELAS_KOSONG",
                "catatan": "Kode kelas kosong.",
            })
        elif not CLASS_PATTERN.match(code):
            out.append({
                "row_id": row.get("_row_id"),
                "sheet_asal": row.get("_sheet_asal_rekap"),
                "nama": str(row.get(name_col, "")) if name_col else "",
                "kode_kelas_pai": code,
                "jenis_masalah": "FORMAT_KODE_KELAS_MENCURIGAKAN",
                "catatan": "Format ideal AI + 3 digit, contoh AI027.",
            })
    return out
