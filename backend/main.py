from __future__ import annotations

import os
import secrets
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.excel_reader import read_master_excel, read_rekap_excel
from app.excel_writer import generate_excel_file
from app.matching import analyze_with_master, analyze_without_master, apply_user_approvals
from app.schemas import ApprovalPayload, GenerateExcelPayload
from app.supabase_lookup import lookup_health, search_lookup_by_nim, update_lookup_from_generated_excel

load_dotenv()

app = FastAPI(title="Rekap Nilai Per Kelas Asli API", version="1.0.0")

origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
allow_all_origins = "*" in origins
allowed_origins = ["*"] if allow_all_origins else origins + ["http://127.0.0.1:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, dict] = {}
DOWNLOADS: dict[str, str] = {}
RUNTIME_AUTH_TOKEN = os.getenv("APP_AUTH_TOKEN") or secrets.token_urlsafe(32)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


def require_admin(authorization: str | None = Header(default=None)) -> bool:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Login admin diperlukan.")
    token = authorization.split(" ", 1)[1].strip()
    if token != RUNTIME_AUTH_TOKEN:
        raise HTTPException(status_code=401, detail="Token admin tidak valid atau sudah kedaluwarsa.")
    return True


@app.get("/api/health")
def health():
    lookup = lookup_health()
    return {
        "status": "ok",
        "groq_available": bool(os.getenv("GROQ_API_KEY")),
        "groq_model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        "public_lookup_storage": lookup.get("storage"),
        "public_lookup_ready": lookup.get("ready"),
        "supabase_configured": lookup.get("configured"),
        "supabase_table": lookup.get("table"),
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
    return search_lookup_by_nim(nim)


@app.post("/api/analyze")
async def analyze(
    mode: str = Form(...),
    use_groq: bool = Form(False),
    rekap_file: UploadFile = File(...),
    master_file: Optional[UploadFile] = File(None),
    _admin: bool = Depends(require_admin),
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
def apply_approvals(payload: ApprovalPayload, _admin: bool = Depends(require_admin)):
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
def generate_excel(payload: GenerateExcelPayload, _admin: bool = Depends(require_admin)):
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

    lookup_info = update_lookup_from_generated_excel(out_path)

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
        raise HTTPException(status_code=404, detail="File download tidak ditemukan atau sudah kedaluwarsa.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Rekap_Nilai_Per_Kelas_Asli_Final.xlsx",
    )
