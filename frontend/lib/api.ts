import { AnalysisResult, Approval, Mode } from "@/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
export const AUTH_TOKEN_KEY = "rekap_nilai_auth_token";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function saveAuthToken(token: string) {
  if (typeof window !== "undefined") window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAuthToken() {
  if (typeof window !== "undefined") window.localStorage.removeItem(AUTH_TOKEN_KEY);
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getAuthToken();
  return {
    ...(extra || {}),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function parseError(res: Response) {
  try {
    const data = await res.json();
    return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data);
  } catch {
    return res.statusText;
  }
}

async function fetchWithFallback(paths: string[], init?: RequestInit): Promise<Response> {
  let lastResponse: Response | null = null;
  for (const path of paths) {
    const res = await fetch(`${API_BASE}${path}`, init);
    lastResponse = res;
    if (res.status !== 404) return res;
  }
  return lastResponse as Response;
}

export async function loginAdmin(username: string, password: string): Promise<{ token: string; username: string }> {
  const res = await fetchWithFallback(["/api/auth/login", "/api/login"], {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  if (data.token) saveAuthToken(data.token);
  return data;
}

export type PublicNimSearchResponse = {
  ready: boolean;
  message: string;
  columns: string[];
  rows: Record<string, any>[];
  query?: string;
  count?: number;
  results?: Record<string, any>[];
};

export async function publicSearchNim(nim: string): Promise<PublicNimSearchResponse> {
  const res = await fetchWithFallback([
    `/api/public/search-nim?nim=${encodeURIComponent(nim)}`,
    `/api/public-search-nim?nim=${encodeURIComponent(nim)}`,
  ]);
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();

  const rows = data.rows || data.results || [];
  const columns = data.columns || (rows[0] ? Object.keys(rows[0]) : ["NIM", "NAMA", "KODE KELAS PAI"]);

  return {
    ready: data.ready ?? true,
    message: data.message || (rows.length ? "Data ditemukan." : "Data tidak ditemukan."),
    columns,
    rows,
    query: data.query,
    count: data.count ?? rows.length,
    results: rows,
  };
}

export const searchPublicNim = publicSearchNim;

export async function analyzeData(args: {
  mode: Mode;
  useGroq: boolean;
  masterFile: File | null;
  rekapFile: File | null;
}): Promise<AnalysisResult> {
  if (!args.rekapFile) throw new Error("Upload file Rekapitulasi Nilai terlebih dahulu.");
  if (args.mode === "with_master" && !args.masterFile) throw new Error("Mode Pakai Data Master membutuhkan file Data Master.");

  const form = new FormData();
  form.append("mode", args.mode);
  form.append("use_groq", String(args.useGroq));
  form.append("rekap_file", args.rekapFile);
  if (args.masterFile) form.append("master_file", args.masterFile);

  const res = await fetch(`${API_BASE}/api/analyze`, { method: "POST", headers: authHeaders(), body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function applyApprovals(sessionId: string, approvals: Approval[]): Promise<AnalysisResult> {
  const res = await fetch(`${API_BASE}/api/apply-approvals`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ session_id: sessionId, approvals }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function generateExcel(sessionId: string, approvals: Approval[]) {
  const res = await fetch(`${API_BASE}/api/generate-excel`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ session_id: sessionId, approvals }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export function downloadUrl(path: string) {
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

function filenameFromDisposition(disposition: string | null): string {
  const match = disposition?.match(/filename="?([^"]+)"?/i);
  return match?.[1] || "Rekap_Nilai_Per_Kelas_Asli_Final.xlsx";
}

export async function downloadExcel(path: string) {
  const res = await fetch(downloadUrl(path), { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));

  const blob = await res.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filenameFromDisposition(res.headers.get("Content-Disposition"));
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}
