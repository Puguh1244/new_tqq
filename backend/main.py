from __future__ import annotations

import os
import secrets
import tempfile
import time
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.excel_reader import read_master_excel, read_rekap_excel
from app.excel_writer import generate_excel_file
from app.matching import analyze_with_master, analyze_without_master, apply_user_approvals, build_preview
from app.schemas import ApprovalPayload, GenerateExcelPayload
from app.supabase_lookup import lookup_health, search_lookup_by_nim, update_lookup_from_generated_excel

load_dotenv()

app = FastAPI(title="Rekap Nilai Per Kelas Asli API", version="1.0.0")

DEFAULT_FRONTEND_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,https://new-tqq.vercel.app"
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", DEFAULT_FRONTEND_ORIGINS).split(",") if x.strip()]
allow_all_origins = "*" in origins and os.getenv("ALLOW_ALL_ORIGINS", "").lower() == "true"
allowed_origins = ["*"] if allow_all_origins else sorted({x for x in origins if x != "*"})
if not allowed_origins:
    allowed_origins = DEFAULT_FRONTEND_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict[str, dict] = {}
DOWNLOADS: dict[str, dict[str, object]] = {}
LOGIN_FAILURES: dict[str, dict[str, float | int]] = {}
RUNTIME_AUTH_TOKEN = os.getenv("APP_AUTH_TOKEN") or secrets.token_urlsafe(32)
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", str(60 * 60)))
DOWNLOAD_TTL_SECONDS = int(os.getenv("DOWNLOAD_TTL_SECONDS", str(60 * 60)))
AUTH_LOCKOUT_MAX_FAILURES = int(os.getenv("AUTH_LOCKOUT_MAX_FAILURES", "5"))
AUTH_LOCKOUT_WINDOW_SECONDS = int(os.getenv("AUTH_LOCKOUT_WINDOW_SECONDS", str(15 * 60)))
UPLOAD_READ_CHUNK_BYTES = 1024 * 1024
XLSX_CONTENT_TYPES = {
    "",
    "application/octet-stream",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


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
    if not secrets.compare_digest(token, RUNTIME_AUTH_TOKEN):
        raise HTTPException(status_code=401, detail="Token admin tidak valid atau sudah kedaluwarsa.")
    return True


def is_production_runtime() -> bool:
    environment = os.getenv("ENVIRONMENT", "").lower()
    return (
        os.getenv("VERCEL") == "1"
        or environment == "production"
        or bool(os.getenv("RENDER"))
        or bool(os.getenv("RAILWAY_ENVIRONMENT"))
        or bool(os.getenv("FLY_APP_NAME"))
        or bool(os.getenv("K_SERVICE"))
    )


def insecure_dev_password_allowed() -> bool:
    return os.getenv("ALLOW_INSECURE_DEV_PASSWORD", "").lower() == "true" and not is_production_runtime()


def get_expected_admin_password() -> str:
    expected_password = os.getenv("ADMIN_PASSWORD")
    if expected_password and expected_password != "admin123":
        return expected_password
    if insecure_dev_password_allowed():
        return expected_password or "admin123"
    if expected_password == "admin123":
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD masih memakai password default. Ganti password admin di backend.")
    raise HTTPException(status_code=500, detail="ADMIN_PASSWORD belum dikonfigurasi di backend.")


def login_failure_key(request: Request, username: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{username.strip().lower()}"


def assert_login_not_locked(key: str) -> None:
    failure = LOGIN_FAILURES.get(key)
    if not failure:
        return
    now = time.time()
    first_failed_at = float(failure.get("first_failed_at", 0))
    if now - first_failed_at > AUTH_LOCKOUT_WINDOW_SECONDS:
        LOGIN_FAILURES.pop(key, None)
        return
    if int(failure.get("count", 0)) >= AUTH_LOCKOUT_MAX_FAILURES:
        raise HTTPException(status_code=429, detail="Terlalu banyak percobaan login gagal. Coba lagi beberapa menit lagi.")


def record_login_failure(key: str) -> None:
    now = time.time()
    failure = LOGIN_FAILURES.get(key)
    if not failure or now - float(failure.get("first_failed_at", 0)) > AUTH_LOCKOUT_WINDOW_SECONDS:
        LOGIN_FAILURES[key] = {"count": 1, "first_failed_at": now}
        return
    failure["count"] = int(failure.get("count", 0)) + 1


def validate_uuid(value: str, label: str) -> None:
    try:
        uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"{label} tidak ditemukan atau sudah kedaluwarsa.") from exc


def prune_expired_state() -> None:
    now = time.time()
    for session_id, session in list(SESSIONS.items()):
        if now - float(session.get("created_at", 0)) > SESSION_TTL_SECONDS:
            SESSIONS.pop(session_id, None)
    for file_id, download in list(DOWNLOADS.items()):
        if now - float(download.get("created_at", 0)) > DOWNLOAD_TTL_SECONDS:
            DOWNLOADS.pop(file_id, None)


def get_session(session_id: str) -> dict:
    validate_uuid(session_id, "Session")
    prune_expired_state()
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session tidak ditemukan atau sudah kedaluwarsa.")
    return session


def refresh_result_preview(session: dict, result):
    preview = build_preview(
        session["rekap"],
        result.mapping,
        session["mode"],
        duplicates=result.duplicates,
        validation_scores=result.validation_scores,
        validation_codes=result.validation_codes,
        missing_scores=result.missing_scores,
        summary=result.summary,
    )
    return result.model_copy(update={"preview": preview})


async def read_xlsx_upload(upload: UploadFile, label: str) -> bytes:
    filename = Path(upload.filename or "").name
    if Path(filename).suffix.lower() != ".xlsx":
        raise HTTPException(status_code=400, detail=f"File {label} harus berformat .xlsx.")

    content_type = (upload.content_type or "").lower()
    if content_type not in XLSX_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"Content-Type file {label} tidak valid untuk .xlsx.")

    contents = bytearray()
    while True:
        chunk = await upload.read(UPLOAD_READ_CHUNK_BYTES)
        if not chunk:
            break
        contents.extend(chunk)
        if len(contents) > MAX_UPLOAD_BYTES:
            max_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"File {label} terlalu besar. Maksimal {max_mb} MB.")

    data = bytes(contents)
    if not data:
        raise HTTPException(status_code=400, detail=f"File {label} kosong.")
    if not zipfile.is_zipfile(BytesIO(data)):
        raise HTTPException(status_code=400, detail=f"File {label} bukan workbook .xlsx yang valid atau corrupt.")
    return data


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
def login(payload: LoginRequest, request: Request):
    expected_username = os.getenv("ADMIN_USERNAME", "admin")
    expected_password = get_expected_admin_password()
    failure_key = login_failure_key(request, payload.username)
    assert_login_not_locked(failure_key)

    username_ok = secrets.compare_digest(payload.username, expected_username)
    password_ok = secrets.compare_digest(payload.password, expected_password)
    if not username_ok or not password_ok:
        record_login_failure(failure_key)
        raise HTTPException(status_code=401, detail="Username atau password salah.")

    LOGIN_FAILURES.pop(failure_key, None)
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

    rekap_bytes = await read_xlsx_upload(rekap_file, "rekap")
    rekap = read_rekap_excel(rekap_bytes)

    master = None
    if mode == "with_master":
        if master_file is None:
            raise HTTPException(status_code=400, detail="Mode Pakai Data Master membutuhkan file Data Master.")
        master_bytes = await read_xlsx_upload(master_file, "master")
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
        "created_at": time.time(),
    }

    payload = result.to_public_dict()
    payload["session_id"] = session_id
    return payload


@app.post("/api/apply-approvals")
def apply_approvals(payload: ApprovalPayload, _admin: bool = Depends(require_admin)):
    session = get_session(payload.session_id)

    result = session["result"]
    updated = refresh_result_preview(session, apply_user_approvals(result, payload.approvals))
    session["result"] = updated

    out = updated.to_public_dict()
    out["session_id"] = payload.session_id
    return out


@app.post("/api/generate-excel")
def generate_excel(payload: GenerateExcelPayload, _admin: bool = Depends(require_admin)):
    session = get_session(payload.session_id)

    if payload.approvals:
        session["result"] = refresh_result_preview(session, apply_user_approvals(session["result"], payload.approvals))

    result = session["result"]
    unresolved = sum(1 for item in result.mapping if item.get("status_mapping") == "NEEDS_CONFIRMATION")
    if unresolved:
        raise HTTPException(
            status_code=400,
            detail=f"Masih ada {unresolved} nama yang perlu dikonfirmasi sebelum generate Excel final.",
        )
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

    DOWNLOADS[file_id] = {"path": str(out_path), "created_at": time.time()}
    return {
        "file_id": file_id,
        "download_url": f"/api/download/{file_id}",
        "status": "ready",
        "public_lookup": lookup_info,
    }


@app.get("/api/download/{file_id}")
def download(file_id: str, _admin: bool = Depends(require_admin)):
    validate_uuid(file_id, "File download")
    prune_expired_state()
    download_info = DOWNLOADS.get(file_id)
    path = str(download_info.get("path")) if download_info else ""
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="File download tidak ditemukan atau sudah kedaluwarsa.")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="Rekap_Nilai_Per_Kelas_Asli_Final.xlsx",
    )
