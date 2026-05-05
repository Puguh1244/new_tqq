from __future__ import annotations

import os
import re
import secrets
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.excel_reader import read_master_excel, read_rekap_excel
from app.excel_writer import generate_excel_file
from app.matching import analyze_with_master, analyze_without_master, apply_user_approvals
from app.schemas import ApprovalPayload, GenerateExcelPayload

load_dotenv()

app = FastAPI(title="Rekap Nilai Per Kelas Asli API", version="1.0.0")

origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins + ["http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, dict] = {}
DOWNLOADS: dict[str, str] = {}
RUNTIME_AUTH_TOKEN = os.getenv("APP_AUTH_TOKEN") or secrets.token_urlsafe(32)

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


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


def public_lookup_path() -> Path:
    configured = os.getenv("PUBLIC_LOOKUP_FILE", "").strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parent / "data" / "public_lookup.xlsx"


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


def safe_cell(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def require_admin(authorization: str | None = Header(default=None)) -> bool:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Login admin diperlukan.")
    token = authorization.split(" ", 1)[1].strip()
    if token != RUNTIME_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin tidak valid atau sudah kedaluwarsa.")
    return True


def update_public_lookup_from_generated_excel(final_excel_path: Path) -> dict:
    """Build public NIM lookup from the generated final workbook.

    IMPORTANT: This reads the final Excel class sheets, not the old 3-column
    summary. Because of that, public search will include score columns and other
    visible final columns exactly as they appear in class sheets.
    """
    lookup_path = public_lookup_path()
    lookup_path.parent.mkdir(parents=True, exist_ok=True)

    if not final_excel_path.exists():
        return {"updated": False, "reason": "Final Excel tidak ditemukan.", "path": str(lookup_path)}

    try:
        workbook = pd.read_excel(final_excel_path, sheet_name=None, dtype=object, engine="openpyxl")
    except Exception as exc:
        return {"updated": False, "reason": f"Gagal membaca Excel final: {exc}", "path": str(lookup_path)}

    frames: list[pd.DataFrame] = []
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

        # If class column is missing for any reason, use the sheet name.
        class_col = find_column(df.columns, CLASS_CANDIDATES)
        if not class_col:
            df["KODE KELAS PAI"] = sheet_name

        frames.append(df)

    if not frames:
        empty = pd.DataFrame(columns=["NIM", "NAMA", "KODE KELAS PAI"])
        empty.to_excel(lookup_path, index=False)
        return {"updated": False, "reason": "Tidak ada sheet kelas yang bisa dipakai.", "path": str(lookup_path)}

    lookup_df = pd.concat(frames, ignore_index=True, sort=False)
    nim_col = find_column(lookup_df.columns, NIM_CANDIDATES)
    name_col = find_column(lookup_df.columns, NAME_CANDIDATES)
    class_col = find_column(lookup_df.columns, CLASS_CANDIDATES)

    if not nim_col:
        empty = pd.DataFrame(columns=["NIM", "NAMA", "KODE KELAS PAI"])
        empty.to_excel(lookup_path, index=False)
        return {"updated": False, "reason": "Kolom NIM/NPM tidak ditemukan di Excel final.", "path": str(lookup_path)}

    # Reorder key columns first, but keep ALL other columns after that.
    ordered: list[str] = []
    for col in [nim_col, name_col, class_col]:
        if col and col in lookup_df.columns and col not in ordered:
            ordered.append(col)
    for col in lookup_df.columns:
        if col not in ordered and not str(col).startswith("_"):
            ordered.append(col)
    lookup_df = lookup_df[ordered]

    lookup_df[nim_col] = lookup_df[nim_col].map(normalize_nim)
    lookup_df = lookup_df[lookup_df[nim_col].astype(str).str.strip() != ""]
    lookup_df = lookup_df.drop_duplicates(subset=[nim_col], keep="last")

    # Make public lookup readable as text and prevent Excel from converting NIM.
    for col in lookup_df.columns:
        lookup_df[col] = lookup_df[col].map(safe_cell)

    lookup_df.to_excel(lookup_path, index=False)
    return {
        "updated": True,
        "path": str(lookup_path),
        "rows": int(len(lookup_df)),
        "columns": [str(c) for c in lookup_df.columns],
        "nim_column": str(nim_col),
    }


def read_public_lookup() -> tuple[pd.DataFrame | None, str | None, str | None]:
    path = public_lookup_path()
    if not path.exists():
        return None, None, "Data pencarian NIM belum tersedia. Login admin, lakukan Analisis, lalu klik Generate Excel Final untuk membuat data pencarian otomatis."
    try:
        df = pd.read_excel(path, dtype=object, engine="openpyxl")
        df.columns = [str(c).replace("\u00a0", " ").strip() for c in df.columns]
    except Exception as exc:
        return None, None, f"Data pencarian NIM gagal dibaca: {exc}"
    nim_col = find_column(df.columns, NIM_CANDIDATES)
    if not nim_col:
        return df, None, "Kolom NIM/NPM tidak ditemukan di data pencarian. Generate Excel Final ulang setelah memasang patch terbaru."
    return df, nim_col, None


@app.get("/api/health")
def health():
    lookup = public_lookup_path()
    return {
        "status": "ok",
        "groq_available": bool(os.getenv("GROQ_API_KEY")),
        "groq_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "public_lookup_ready": lookup.exists(),
        "public_lookup_file": str(lookup),
    }


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest):
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = os.getenv("ADMIN_PASSWORD", "admin123")
    if payload.username != expected_username or payload.password != expected_password:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    return LoginResponse(token=RUNTIME_AUTH_TOKEN, username=payload.username)


@app.get("/api/public/search-nim")
def public_search_nim(nim: str = Query(..., min_length=1)):
    df, nim_col, error = read_public_lookup()
    if error:
        return {
            "ready": False,
            "message": error,
            "columns": [],
            "rows": [],
        }

    assert df is not None and nim_col is not None
    q = normalize_nim(nim)
    df = df.copy()
    df[nim_col] = df[nim_col].map(normalize_nim)
    matches = df[df[nim_col] == q]
    if matches.empty:
        # fallback contains for users typing partial NIM
        matches = df[df[nim_col].astype(str).str.contains(re.escape(q), na=False)]

    rows = []
    for record in matches.head(20).to_dict("records"):
        rows.append({str(k): safe_cell(v) for k, v in record.items()})

    return {
        "ready": True,
        "message": "Data ditemukan." if rows else "NIM tidak ditemukan.",
        "columns": [str(c) for c in df.columns],
        "rows": rows,
    }


@app.post("/api/analyze")
async def analyze(
    mode: str = Form(...),
    use_groq: bool = Form(False),
    rekap_file: UploadFile = File(...),
    master_file: Optional[UploadFile] = File(None),
):
    if mode not in {"with_master", "without_master"}:
        raise HTTPException(status_code=400, detail="Mode harus with_master atau without_master.")

    rekap_bytes = await rekap_file.read()
    rekap = read_rekap_excel(rekap_bytes)

    master = None
    if mode == "with_master":
        if master_file is None:
            raise HTTPException(status_code=400, detail="Mode Pakai Data Master membutuhkan file Data Master.")
        master_bytes = await master_file.read()
        master = read_master_excel(master_bytes)
        result = analyze_with_master(rekap, master, use_groq=use_groq)
    else:
        result = analyze_without_master(rekap)

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "mode": mode,
        "rekap": rekap,
        "master": master,
        "result": result,
    }

    payload = result.to_public_dict()
    payload["session_id"] = session_id
    return payload


@app.post("/api/apply-approvals")
def apply_approvals(payload: ApprovalPayload):
    session = SESSIONS.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan atau sudah kedaluwarsa.")

    result = session["result"]
    updated = apply_user_approvals(result, payload.approvals)
    session["result"] = updated

    out = updated.to_public_dict()
    out["session_id"] = payload.session_id
    return out


@app.post("/api/generate-excel")
def generate_excel(payload: GenerateExcelPayload):
    session = SESSIONS.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan atau sudah kedaluwarsa.")

    if payload.approvals:
        session["result"] = apply_user_approvals(session["result"], payload.approvals)

    result = session["result"]
    if result.summary.get("total_mapped", 0) == 0 and session["mode"] == "with_master":
        raise HTTPException(status_code=400, detail="Tidak ada data berhasil dipetakan. Periksa file atau approval nama.")

    file_id = str(uuid.uuid4())
    out_dir = Path(tempfile.gettempdir()) / "rekap_nilai_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"rekap_nilai_final_{file_id}.xlsx"

    generate_excel_file(
        out_path=out_path,
        mode=session["mode"],
        rekap=session["rekap"],
        result=result,
    )

    lookup_info = update_public_lookup_from_generated_excel(out_path)

    DOWNLOADS[file_id] = str(out_path)
    return {
        "file_id": file_id,
        "download_url": f"/api/download/{file_id}",
        "status": "ready",
        "public_lookup": lookup_info,
    }


@app.get("/api/download/{file_id}")
def download(file_id: str):
    path = DOWNLOADS.get(file_id)
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="File download tidak ditemukan.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Rekap_Nilai_Per_Kelas_Asli_Final.xlsx",
    )
