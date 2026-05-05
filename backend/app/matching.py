from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
from fastapi import HTTPException
from rapidfuzz import fuzz, process

from app.excel_reader import ExcelData
from app.groq_client import ask_groq_for_match, groq_status
from app.schemas import AnalysisResult, ApprovalItem
from app.validation import validate_class_codes, validate_scores


def safe_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_name(value: Any) -> str:
    text = safe_str(value).lower().replace("\u00a0", " ")
    text = re.sub(r"[\u200b-\u200d\ufeff]", "", text)
    text = re.sub(r"[^a-z0-9\s\.'`-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_class(value: Any) -> str:
    return safe_str(value).upper().replace(" ", "")


SOURCE_NUMBER_HEADERS = {"NO", "NOMOR", "NOURUT", "NOMORURUT", "NUMBER", "NUM"}


def normalize_header(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").strip().upper())


def is_source_number_column(column: Any) -> bool:
    """Detect source row-number columns such as NO, No., Nomor, Nomor Urut."""
    return normalize_header(column) in SOURCE_NUMBER_HEADERS


def duplicate_rows(df: pd.DataFrame, name_col: str, source: str) -> list[dict[str, Any]]:
    norms = df[name_col].map(normalize_name)
    counts = Counter(norms)
    out = []
    for idx, row in df.iterrows():
        norm = norms.loc[idx]
        if norm and counts[norm] > 1:
            out.append({
                "source": source,
                "nama": safe_str(row.get(name_col)),
                "nama_normalized": norm,
                "count": counts[norm],
                "sheet_asal": row.get("_sheet_asal_rekap", ""),
                "row_id": row.get("_row_id", ""),
            })
    return out


def build_dashboard(result: dict[str, Any]) -> dict[str, Any]:
    mapping = result["mapping"]
    status_counts = Counter(x.get("status_mapping") for x in mapping)
    class_counts = Counter(x.get("kode_kelas_pai") for x in mapping if x.get("kode_kelas_pai"))
    suspicious_by_class = Counter(x.get("kode_kelas_pai") for x in result.get("validation_scores", []) if x.get("kode_kelas_pai"))

    by_sheet: dict[str, Counter] = defaultdict(Counter)
    for item in mapping:
        by_sheet[item.get("sheet_asal_rekap", "")][item.get("status_mapping")] += 1

    top_classes = [
        {
            "kode_kelas": k,
            "jumlah_mahasiswa": int(v),
            "exact": sum(1 for x in mapping if x.get("kode_kelas_pai") == k and x.get("status_mapping") == "EXACT_MATCH"),
            "perlu_konfirmasi": sum(1 for x in mapping if x.get("kode_kelas_pai") == k and x.get("status_mapping") == "NEEDS_CONFIRMATION"),
            "suspicious_scores": int(suspicious_by_class.get(k, 0)),
        }
        for k, v in class_counts.most_common(10)
    ]

    trends = []
    for sheet, counts in by_sheet.items():
        trends.append({
            "sheet": sheet,
            "exact": int(counts.get("EXACT_MATCH", 0)),
            "normalized": int(counts.get("NORMALIZED_MATCH", 0)),
            "perlu_konfirmasi": int(counts.get("NEEDS_CONFIRMATION", 0)),
            "unmapped": int(counts.get("UNMAPPED", 0)),
        })

    score_issues = result.get("validation_scores", [])
    return {
        "status_distribution": [
            {"name": "Exact Match", "value": int(status_counts.get("EXACT_MATCH", 0))},
            {"name": "Normalized Match", "value": int(status_counts.get("NORMALIZED_MATCH", 0))},
            {"name": "Perlu Konfirmasi", "value": int(status_counts.get("NEEDS_CONFIRMATION", 0))},
            {"name": "Unmapped", "value": int(status_counts.get("UNMAPPED", 0))},
        ],
        "top_classes": top_classes,
        "score_summary": [
            {"name": "Nilai Kosong", "value": sum(1 for x in score_issues if x.get("jenis_masalah") == "NILAI_KOSONG")},
            {"name": "> 100", "value": sum(1 for x in score_issues if x.get("jenis_masalah") in ["NILAI_LEBIH_DARI_100", "TOTAL_NILAI_MENCURIGAKAN"])},
            {"name": "< 0", "value": sum(1 for x in score_issues if x.get("jenis_masalah") == "NILAI_KURANG_DARI_0")},
            {"name": "Total Mencurigakan", "value": len(score_issues)},
        ],
        "trends": trends,
    }


def preview_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, dict, set)):
        return value
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return value


def make_class_preview_df(rows: list[dict[str, Any]], final_class: str, class_col: str | None) -> pd.DataFrame:
    """Create a preview that mirrors the final Excel class sheet."""
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Remove internal technical columns and source row-number columns, then
    # recreate NO from 1 for each sheet. This also catches NO., Nomor, etc.
    drop_cols = [c for c in df.columns if str(c).startswith("_") or is_source_number_column(c)]
    df = df.drop(columns=drop_cols, errors="ignore")

    if class_col and class_col in df.columns:
        df[class_col] = final_class
    else:
        df["KODE KELAS PAI"] = final_class

    df.insert(0, "NO", range(1, len(df) + 1))
    return df.fillna("")


def records_for_preview(records: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    return [
        {
            str(k): preview_value(v)
            for k, v in row.items()
            if not str(k).startswith("_") and not is_source_number_column(k)
        }
        for row in records[:limit]
    ]


def build_preview(
    rekap: ExcelData,
    mapping: list[dict[str, Any]],
    mode: str,
    duplicates: list[dict[str, Any]] | None = None,
    validation_scores: list[dict[str, Any]] | None = None,
    validation_codes: list[dict[str, Any]] | None = None,
    missing_scores: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an Excel-like preview payload.

    Frontend can render this as clickable sheet tabs. Each class sheet preview
    follows final Excel rules: clean columns, final KODE KELAS PAI, and NO reset
    from 1. Audit previews are separate so BELUM_TERPETAKAN is not mixed into
    the class sheet list.
    """
    duplicates = duplicates or []
    validation_scores = validation_scores or []
    validation_codes = validation_codes or []
    missing_scores = missing_scores or []
    summary = summary or {}

    mapped = {m["row_id"]: m for m in mapping}
    class_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unmapped_rows: list[dict[str, Any]] = []

    for _, row in rekap.df.iterrows():
        row_id = row.get("_row_id")
        row_dict = row.to_dict()
        m = mapped.get(row_id, {})

        if mode == "without_master":
            final_class = normalize_class(row.get(rekap.class_col)) if rekap.class_col else ""
            is_mapped = bool(final_class)
        else:
            final_class = normalize_class(m.get("kode_kelas_pai"))
            is_mapped = (
                m.get("status_mapping")
                in {"EXACT_MATCH", "NORMALIZED_MATCH", "FUZZY_HIGH_CONFIDENCE", "APPROVED_BY_USER"}
                and bool(final_class)
            )

        if is_mapped:
            class_rows[final_class].append(row_dict)
        else:
            clean = {
                str(k): preview_value(v)
                for k, v in row_dict.items()
                if not str(k).startswith("_") and not is_source_number_column(k)
            }
            clean.update({
                "STATUS MAPPING": m.get("status_mapping", "UNMAPPED"),
                "NAMA MASTER": m.get("nama_master", ""),
                "CONFIDENCE": m.get("confidence", 0),
                "CATATAN": m.get("catatan", ""),
            })
            unmapped_rows.append(clean)

    class_sheets = []
    for sheet_name, rows in sorted(class_rows.items(), key=lambda item: (-len(item[1]), item[0])):
        df = make_class_preview_df(rows, sheet_name, rekap.class_col)
        class_sheets.append({
            "sheet": sheet_name,
            "type": "class",
            "rows": int(len(df)),
            "columns": [str(c) for c in df.columns],
            "preview_rows": df.head(30).to_dict("records"),
        })

    audit_definitions = [
        ("LOG_MAPPING", mapping),
        ("PERLU_KONFIRMASI", [x for x in mapping if x.get("status_mapping") == "NEEDS_CONFIRMATION"]),
        ("BELUM_TERPETAKAN", unmapped_rows),
        ("NAMA_DUPLIKAT", duplicates),
        ("BELUM_ADA_NILAI", missing_scores),
        ("VALIDASI_NILAI", validation_scores),
        ("VALIDASI_KODE", validation_codes),
        ("RINGKASAN", [summary]),
    ]

    audit_sheets = []
    for name, records in audit_definitions:
        preview_rows = records_for_preview(records, limit=30)
        columns = list(preview_rows[0].keys()) if preview_rows else []
        audit_sheets.append({
            "sheet": name,
            "type": "audit",
            "rows": int(len(records)),
            "columns": columns,
            "preview_rows": preview_rows,
        })

    first_sheet_rows = class_sheets[0]["preview_rows"] if class_sheets else []

    return {
        "class_sheets": class_sheets,
        "audit_sheets": audit_sheets,
        "sample_rows": first_sheet_rows,
    }


def analyze_with_master(rekap: ExcelData, master: ExcelData, use_groq: bool = False) -> AnalysisResult:
    rname = rekap.name_col
    mname = master.name_col
    mclass = master.class_col
    assert rname and mname and mclass

    mdf = master.df.copy()
    mdf["_nama_norm"] = mdf[mname].map(normalize_name)
    norm_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, norm in mdf["_nama_norm"].items():
        if norm:
            norm_to_indices[norm].append(idx)

    exact_to_indices: dict[str, list[int]] = defaultdict(list)
    for idx, val in mdf[mname].items():
        if safe_str(val):
            exact_to_indices[safe_str(val)].append(idx)

    choices = sorted(set(x for x in mdf["_nama_norm"].tolist() if x))

    mapping: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []

    for _, row in rekap.df.iterrows():
        nama = safe_str(row.get(rname))
        norm = normalize_name(nama)
        row_id = row.get("_row_id")
        base = {
            "mapping_id": row_id,
            "row_id": row_id,
            "nama_rekap": nama,
            "nama_rekap_normalized": norm,
            "nama_master": "",
            "nama_master_normalized": "",
            "kode_kelas_pai": "",
            "sheet_asal_rekap": row.get("_sheet_asal_rekap"),
            "status_mapping": "UNMAPPED",
            "match_method": "NONE",
            "confidence": 0,
            "approved_by_user": False,
            "catatan": "Tidak ditemukan kandidat yang cukup dekat.",
        }

        exact_hits = exact_to_indices.get(nama, [])
        if len(exact_hits) == 1:
            hit = mdf.loc[exact_hits[0]]
            base.update({
                "nama_master": safe_str(hit.get(mname)),
                "nama_master_normalized": safe_str(hit.get("_nama_norm")),
                "kode_kelas_pai": normalize_class(hit.get(mclass)),
                "status_mapping": "EXACT_MATCH",
                "match_method": "EXACT",
                "confidence": 100,
                "catatan": "Nama sama persis dengan Data Master.",
            })
            mapping.append(base)
            continue

        norm_hits = norm_to_indices.get(norm, [])
        if len(norm_hits) == 1:
            hit = mdf.loc[norm_hits[0]]
            base.update({
                "nama_master": safe_str(hit.get(mname)),
                "nama_master_normalized": safe_str(hit.get("_nama_norm")),
                "kode_kelas_pai": normalize_class(hit.get(mclass)),
                "status_mapping": "NORMALIZED_MATCH",
                "match_method": "NORMALIZED",
                "confidence": 100,
                "catatan": "Cocok setelah normalisasi nama.",
            })
            mapping.append(base)
            continue
        if len(norm_hits) > 1:
            base.update({"status_mapping": "DUPLICATE_MASTER", "catatan": "Nama normalized ditemukan lebih dari satu di Data Master."})
            mapping.append(base)
            continue

        candidates = []
        if norm and choices:
            for cand_norm, score, _ in process.extract(norm, choices, scorer=fuzz.WRatio, limit=5):
                idx = norm_to_indices[cand_norm][0]
                hit = mdf.loc[idx]
                candidates.append({
                    "name": safe_str(hit.get(mname)),
                    "class": normalize_class(hit.get(mclass)),
                    "score": float(score),
                    "normalized": cand_norm,
                })

        best = candidates[0] if candidates else None
        if best and best["score"] >= 96:
            base.update({
                "nama_master": best["name"],
                "nama_master_normalized": best["normalized"],
                "kode_kelas_pai": best["class"],
                "status_mapping": "FUZZY_HIGH_CONFIDENCE",
                "match_method": "FUZZY_LOCAL",
                "confidence": round(best["score"], 2),
                "catatan": "Fuzzy lokal confidence tinggi; tetap tercatat di LOG_MAPPING.",
            })
        elif best and best["score"] >= 85:
            groq_result = ask_groq_for_match(nama, candidates) if use_groq else None
            suggested = best
            reason = "Perlu konfirmasi user berdasarkan fuzzy lokal."
            if groq_result and groq_result.get("matched_name"):
                for c in candidates:
                    if c["name"] == groq_result["matched_name"]:
                        suggested = c
                        break
                reason = groq_result.get("reason") or reason
            base.update({
                "nama_master": suggested["name"],
                "nama_master_normalized": suggested["normalized"],
                "kode_kelas_pai": suggested["class"],
                "status_mapping": "NEEDS_CONFIRMATION",
                "match_method": "GROQ_SUGGESTION" if groq_result and groq_result.get("matched_name") else "FUZZY_LOCAL",
                "confidence": round(float(groq_result.get("confidence", suggested["score"])) if groq_result else suggested["score"], 2),
                "catatan": reason,
                "candidates": candidates,
                "groq": groq_result,
            })
            recommendations.append(base.copy())
        else:
            base.update({
                "status_mapping": "UNMAPPED",
                "match_method": "FUZZY_LOCAL",
                "confidence": round(best["score"], 2) if best else 0,
                "catatan": "Tidak ada kandidat dengan similarity minimal 85.",
                "candidates": candidates,
            })
        mapping.append(base)

    duplicates = duplicate_rows(rekap.df, rname, "REKAP") + duplicate_rows(master.df, mname, "MASTER")
    validation_scores, missing_scores = validate_scores(rekap.df, rname)
    validation_codes = validate_class_codes(master.df, mclass, mname)

    status_counts = Counter(x["status_mapping"] for x in mapping)
    total_mapped = sum(status_counts.get(s, 0) for s in ["EXACT_MATCH", "NORMALIZED_MATCH", "FUZZY_HIGH_CONFIDENCE", "APPROVED_BY_USER"])
    summary = {
        "mode": "Pakai Data Master",
        "total_mahasiswa_rekap": len(rekap.df),
        "total_sheet_rekap": len(rekap.sheets),
        "jumlah_kelas": len(set(x.get("kode_kelas_pai") for x in mapping if x.get("kode_kelas_pai"))),
        "exact_match": status_counts.get("EXACT_MATCH", 0),
        "normalized_match": status_counts.get("NORMALIZED_MATCH", 0),
        "perlu_konfirmasi": status_counts.get("NEEDS_CONFIRMATION", 0),
        "tidak_ditemukan": status_counts.get("UNMAPPED", 0),
        "duplikat": len(duplicates),
        "nilai_mencurigakan": len(validation_scores),
        "belum_ada_nilai": len(missing_scores),
        "total_mapped": total_mapped,
        "groq": groq_status(),
    }

    dashboard = build_dashboard({"mapping": mapping, "validation_scores": validation_scores, "summary": summary})
    preview = build_preview(
        rekap,
        mapping,
        "with_master",
        duplicates=duplicates,
        validation_scores=validation_scores,
        validation_codes=validation_codes,
        missing_scores=missing_scores,
        summary=summary,
    )

    return AnalysisResult(
        mode="with_master",
        summary=summary,
        mapping=mapping,
        recommendations=recommendations,
        duplicates=duplicates,
        validation_scores=validation_scores,
        validation_codes=validation_codes,
        missing_scores=missing_scores,
        preview=preview,
        dashboard=dashboard,
    )


def analyze_without_master(rekap: ExcelData) -> AnalysisResult:
    if not rekap.class_col:
        raise HTTPException(
            status_code=400,
            detail={"message": "Mode Tanpa Data Master membutuhkan kolom KODE KELAS PAI di file rekap.", "columns": list(map(str, rekap.df.columns))}
        )

    mapping = []
    for _, row in rekap.df.iterrows():
        klass = normalize_class(row.get(rekap.class_col))
        mapping.append({
            "mapping_id": row.get("_row_id"),
            "row_id": row.get("_row_id"),
            "nama_rekap": safe_str(row.get(rekap.name_col)),
            "nama_rekap_normalized": normalize_name(row.get(rekap.name_col)),
            "nama_master": "",
            "nama_master_normalized": "",
            "kode_kelas_pai": klass,
            "sheet_asal_rekap": row.get("_sheet_asal_rekap"),
            "status_mapping": "DIRECT_FROM_REKAP",
            "match_method": "KODE_KELAS_REKAP",
            "confidence": 100 if klass else 0,
            "approved_by_user": True,
            "catatan": "Mode Tanpa Data Master: kelas diambil langsung dari rekap.",
        })

    duplicates = duplicate_rows(rekap.df, rekap.name_col, "REKAP") if rekap.name_col else []
    validation_scores, missing_scores = validate_scores(rekap.df, rekap.name_col)
    validation_codes = validate_class_codes(rekap.df, rekap.class_col, rekap.name_col)

    classes = set(x.get("kode_kelas_pai") for x in mapping if x.get("kode_kelas_pai"))
    summary = {
        "mode": "Tanpa Data Master",
        "total_mahasiswa_rekap": len(rekap.df),
        "total_sheet_rekap": len(rekap.sheets),
        "jumlah_kelas": len(classes),
        "exact_match": 0,
        "normalized_match": 0,
        "perlu_konfirmasi": 0,
        "tidak_ditemukan": sum(1 for x in mapping if not x.get("kode_kelas_pai")),
        "duplikat": len(duplicates),
        "nilai_mencurigakan": len(validation_scores),
        "belum_ada_nilai": len(missing_scores),
        "total_mapped": sum(1 for x in mapping if x.get("kode_kelas_pai")),
        "groq": {"available": False, "model": None},
    }
    dashboard = build_dashboard({"mapping": mapping, "validation_scores": validation_scores, "summary": summary})
    preview = build_preview(
        rekap,
        mapping,
        "without_master",
        duplicates=duplicates,
        validation_scores=validation_scores,
        validation_codes=validation_codes,
        missing_scores=missing_scores,
        summary=summary,
    )

    return AnalysisResult(
        mode="without_master",
        summary=summary,
        mapping=mapping,
        recommendations=[],
        duplicates=duplicates,
        validation_scores=validation_scores,
        validation_codes=validation_codes,
        missing_scores=missing_scores,
        preview=preview,
        dashboard=dashboard,
    )


def apply_user_approvals(result: AnalysisResult, approvals: list[ApprovalItem]) -> AnalysisResult:
    approval_map = {a.mapping_id: a for a in approvals}
    new_mapping = []
    for item in result.mapping:
        updated = dict(item)
        approval = approval_map.get(str(item.get("mapping_id")))
        if approval:
            if approval.approved:
                updated["status_mapping"] = "APPROVED_BY_USER"
                updated["approved_by_user"] = True
                if approval.matched_name:
                    updated["nama_master"] = approval.matched_name
                if approval.matched_class:
                    updated["kode_kelas_pai"] = normalize_class(approval.matched_class)
                updated["catatan"] = "Rekomendasi disetujui user."
            else:
                updated["status_mapping"] = "REJECTED_BY_USER"
                updated["approved_by_user"] = False
                updated["catatan"] = "Rekomendasi ditolak user; data masuk BELUM_TERPETAKAN."
        new_mapping.append(updated)

    status_counts = Counter(x["status_mapping"] for x in new_mapping)
    summary = dict(result.summary)
    summary["perlu_konfirmasi"] = status_counts.get("NEEDS_CONFIRMATION", 0)
    summary["tidak_ditemukan"] = status_counts.get("UNMAPPED", 0) + status_counts.get("REJECTED_BY_USER", 0)
    summary["total_mapped"] = sum(status_counts.get(s, 0) for s in ["EXACT_MATCH", "NORMALIZED_MATCH", "FUZZY_HIGH_CONFIDENCE", "APPROVED_BY_USER", "DIRECT_FROM_REKAP"])
    summary["jumlah_kelas"] = len(set(x.get("kode_kelas_pai") for x in new_mapping if x.get("kode_kelas_pai") and x.get("status_mapping") not in {"UNMAPPED", "REJECTED_BY_USER"}))

    data = result.model_dump()
    data["mapping"] = new_mapping
    data["summary"] = summary
    data["dashboard"] = build_dashboard({"mapping": new_mapping, "validation_scores": result.validation_scores, "summary": summary})
    data["recommendations"] = [x for x in new_mapping if x.get("status_mapping") == "NEEDS_CONFIRMATION"]
    return AnalysisResult(**data)
