from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

AUDIT_SHEETS = {
    "LOG_MAPPING",
    "PERLU_KONFIRMASI",
    "BELUM_TERPETAKAN",
    "NAMA_DUPLIKAT",
    "BELUM_ADA_NILAI",
    "VALIDASI_NILAI",
    "VALIDASI_KODE",
    "RINGKASAN",
}

NIM_CANDIDATES = [
    "NIM",
    "NPM",
    "NO INDUK",
    "NOMOR INDUK",
    "NIM MAHASISWA",
    "NPM MAHASISWA",
]
NAME_CANDIDATES = ["NAMA", "NAMA MAHASISWA", "NAMA LENGKAP", "NAME"]
CLASS_CANDIDATES = ["KODE KELAS PAI", "KELAS PAI", "KODE KELAS", "KELAS"]


def normalize_header(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ").strip().upper())


def find_column(columns, candidates: list[str]) -> str | None:
    normalized = {normalize_header(c): c for c in columns}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for col in columns:
        up = normalize_header(col)
        for candidate in candidates:
            if candidate in up:
                return col
    return None


def normalize_nim(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    # Excel sometimes stores NIM as 25080694316.0
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    return re.sub(r"\s+", "", text)


def jsonable(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def supabase_table_name() -> str:
    return os.getenv("SUPABASE_LOOKUP_TABLE", "public_lookup").strip() or "public_lookup"


def supabase_config() -> tuple[str, str, str]:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    table = supabase_table_name()
    if not url or not key:
        raise RuntimeError(
            "Supabase belum dikonfigurasi. Isi SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY di environment backend."
        )
    return url, key, table


def get_supabase_client():
    url, key, _table = supabase_config()
    try:
        from supabase import create_client
    except Exception as exc:
        raise RuntimeError("Package supabase belum terinstall. Jalankan pip install -r requirements.txt.") from exc
    return create_client(url, key)


def lookup_health() -> dict[str, Any]:
    configured = bool(os.getenv("SUPABASE_URL", "").strip() and os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip())
    return {
        "storage": "supabase",
        "configured": configured,
        "ready": configured,
        "table": supabase_table_name(),
    }


def build_lookup_rows_from_generated_excel(final_excel_path: Path) -> list[dict[str, Any]]:
    """Read final Excel workbook and build public lookup rows.

    This reads class sheets from the generated final Excel, not audit sheets.
    Every visible column in class sheets is preserved inside data JSON.
    """
    if not final_excel_path.exists():
        raise RuntimeError("Final Excel tidak ditemukan.")

    workbook = pd.read_excel(final_excel_path, sheet_name=None, dtype=object, engine="openpyxl")

    by_nim: dict[str, dict[str, Any]] = {}
    for sheet_name, df in workbook.items():
        if normalize_header(sheet_name) in AUDIT_SHEETS:
            continue
        if df is None or df.empty:
            continue

        df = df.copy()
        df.columns = [str(c).replace("\u00a0", " ").strip() for c in df.columns]
        df = df.dropna(how="all")
        if df.empty:
            continue

        nim_col = find_column(df.columns, NIM_CANDIDATES)
        if not nim_col:
            continue

        name_col = find_column(df.columns, NAME_CANDIDATES)
        class_col = find_column(df.columns, CLASS_CANDIDATES)

        for _idx, row in df.iterrows():
            nim = normalize_nim(row.get(nim_col))
            if not nim:
                continue

            nama = jsonable(row.get(name_col)) if name_col else ""
            kode_kelas = jsonable(row.get(class_col)) if class_col else str(sheet_name)

            data: dict[str, Any] = {}
            # Canonical columns first so frontend table is readable.
            data["NIM"] = nim
            data["NAMA"] = nama
            data["KODE KELAS PAI"] = kode_kelas

            for col in df.columns:
                col_name = str(col)
                if col_name.startswith("_"):
                    continue
                if normalize_header(col_name) in {"NIM", "NAMA", "KODE KELAS PAI"}:
                    continue
                data[col_name] = jsonable(row.get(col))

            by_nim[nim] = {
                "nim": nim,
                "nama": nama,
                "kode_kelas_pai": kode_kelas,
                "data": data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

    return list(by_nim.values())


def update_lookup_from_generated_excel(final_excel_path: Path) -> dict[str, Any]:
    """Replace Supabase public lookup with rows from final Excel."""
    try:
        rows = build_lookup_rows_from_generated_excel(final_excel_path)
        client = get_supabase_client()
        table = supabase_table_name()

        # Clear old lookup so public search always reflects the latest generated workbook.
        # This deletes rows where nim is not an impossible sentinel.
        client.table(table).delete().neq("nim", "__never_match__").execute()

        if rows:
            batch_size = 500
            for start in range(0, len(rows), batch_size):
                batch = rows[start : start + batch_size]
                client.table(table).upsert(batch, on_conflict="nim").execute()

        return {
            "updated": True,
            "storage": "supabase",
            "table": table,
            "rows": len(rows),
            "columns": list(rows[0]["data"].keys()) if rows else ["NIM", "NAMA", "KODE KELAS PAI"],
        }
    except Exception as exc:
        return {
            "updated": False,
            "storage": "supabase",
            "table": supabase_table_name(),
            "rows": 0,
            "reason": str(exc),
        }


def _public_row(record: dict[str, Any]) -> dict[str, Any]:
    data = record.get("data") if isinstance(record.get("data"), dict) else {}
    out: dict[str, Any] = {}
    out["NIM"] = jsonable(data.get("NIM") or record.get("nim"))
    out["NAMA"] = jsonable(data.get("NAMA") or record.get("nama"))
    out["KODE KELAS PAI"] = jsonable(data.get("KODE KELAS PAI") or record.get("kode_kelas_pai"))

    for key, value in data.items():
        if key not in out:
            out[str(key)] = jsonable(value)
    return out


def search_lookup_by_nim(nim: str) -> dict[str, Any]:
    q = normalize_nim(nim)
    if not q:
        return {"ready": True, "message": "Masukkan NIM.", "columns": ["NIM", "NAMA", "KODE KELAS PAI"], "rows": []}

    try:
        client = get_supabase_client()
        table = supabase_table_name()

        exact = client.table(table).select("nim,nama,kode_kelas_pai,data").eq("nim", q).limit(20).execute()
        records = exact.data or []

        if not records:
            contains = client.table(table).select("nim,nama,kode_kelas_pai,data").ilike("nim", f"%{q}%").limit(20).execute()
            records = contains.data or []

        rows = [_public_row(record) for record in records]
        columns: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in columns:
                    columns.append(key)
        if not columns:
            columns = ["NIM", "NAMA", "KODE KELAS PAI"]

        return {
            "ready": True,
            "message": "Data ditemukan." if rows else "NIM tidak ditemukan.",
            "columns": columns,
            "rows": rows,
            "count": len(rows),
            "storage": "supabase",
        }
    except Exception as exc:
        return {
            "ready": False,
            "message": f"Data pencarian belum siap atau Supabase belum tersambung: {exc}",
            "columns": ["NIM", "NAMA", "KODE KELAS PAI"],
            "rows": [],
            "count": 0,
            "storage": "supabase",
        }
