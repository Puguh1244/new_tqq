from __future__ import annotations

import json
import os
from typing import Any


def groq_status() -> dict[str, Any]:
    return {
        "available": bool(os.getenv("GROQ_API_KEY")),
        "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    }


def ask_groq_for_match(nama_rekap: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not os.getenv("GROQ_API_KEY"):
        return None

    try:
        from groq import Groq
    except Exception:
        return None

    safe_candidates = [
        {
            "name": str(c.get("name", "")),
            "class": str(c.get("class", "")),
            "score": float(c.get("score", 0)),
        }
        for c in candidates[:5]
    ]

    system = (
        "Kamu membantu validasi typo nama mahasiswa. "
        "Pilih hanya dari kandidat yang diberikan. Jangan mengarang nama. "
        "Kembalikan JSON valid saja sesuai schema."
    )
    user = {
        "nama_rekap_bermasalah": nama_rekap,
        "kandidat_master": safe_candidates,
        "schema": {
            "status": "possible_match | no_match | ambiguous",
            "matched_name": "nama kandidat master atau null",
            "matched_class": "kode kelas atau null",
            "confidence": "0-100",
            "reason": "alasan singkat",
            "action": "auto_suggest | needs_confirmation | reject",
        },
    }

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        completion = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content or "{}"
        data = json.loads(raw)
        names = {c["name"] for c in safe_candidates}
        if data.get("matched_name") and data["matched_name"] not in names:
            data["status"] = "no_match"
            data["matched_name"] = None
            data["matched_class"] = None
            data["action"] = "reject"
        return data
    except Exception as exc:
        return {
            "status": "error",
            "matched_name": None,
            "matched_class": None,
            "confidence": 0,
            "reason": f"Groq gagal: {exc}",
            "action": "reject",
        }
