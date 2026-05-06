"use client";

import { useEffect, useMemo, useState } from "react";
import { LogOut } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { DashboardPage } from "@/components/pages/DashboardPage";
import { AnalisisPage } from "@/components/pages/AnalisisPage";
import { ValidasiNamaPage } from "@/components/pages/ValidasiNamaPage";
import { ValidasiNilaiPage } from "@/components/pages/ValidasiNilaiPage";
import { PreviewOutputPage } from "@/components/pages/PreviewOutputPage";
import { DownloadPage } from "@/components/pages/DownloadPage";
import { PublicSearchPage } from "@/components/pages/PublicSearchPage";
import { analyzeData, applyApprovals, clearAuthToken, downloadExcel, generateExcel, getAuthToken } from "@/lib/api";
import { AnalysisResult, Approval, Mode, PageKey } from "@/types";

export default function Home() {
  const [authChecked, setAuthChecked] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [page, setPage] = useState<PageKey>("analisis");
  const [mode, setMode] = useState<Mode>("with_master");
  const [masterFile, setMasterFile] = useState<File | null>(null);
  const [rekapFile, setRekapFile] = useState<File | null>(null);
  const [useGroq, setUseGroq] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [downloadPath, setDownloadPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    setIsLoggedIn(Boolean(getAuthToken()));
    setAuthChecked(true);
  }, []);

  const filteredResult = useMemo(() => {
    if (!result || !search.trim()) return result;
    const q = search.toLowerCase();
    return {
      ...result,
      mapping: result.mapping.filter((x) => String(x.nama_rekap || "").toLowerCase().includes(q)),
    };
  }, [result, search]);

  async function onAnalyze() {
    setLoading(true); setError(null); setDownloadPath(null);
    try {
      const data = await analyzeData({ mode, useGroq, masterFile, rekapFile });
      setResult(data); setApprovals([]); setPage("dashboard");
    } catch (e: any) { setError(e.message || "Gagal analisis."); }
    finally { setLoading(false); }
  }

  async function onApply() {
    if (!result) return;
    setError(null);
    try {
      const data = await applyApprovals(result.session_id, approvals);
      setResult(data); setPage("preview");
    } catch (e: any) { setError(e.message || "Gagal menerapkan approval."); }
  }

  async function onGenerate() {
    if (!result) { setPage("analisis"); return; }
    setGenerating(true); setError(null);
    try {
      const out = await generateExcel(result.session_id, approvals);
      setDownloadPath(out.download_url); setPage("download");
    } catch (e: any) { setError(e.message || "Gagal generate Excel."); }
    finally { setGenerating(false); }
  }

  async function onDownload() {
    if (!downloadPath) return;
    setDownloading(true); setError(null);
    try {
      await downloadExcel(downloadPath);
    } catch (e: any) {
      setError(e.message || "Gagal download Excel.");
    } finally {
      setDownloading(false);
    }
  }

  function logout() {
    clearAuthToken();
    setIsLoggedIn(false);
    setPage("analisis");
    setResult(null);
    setApprovals([]);
    setDownloadPath(null);
    setError(null);
  }

  if (!authChecked) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm font-semibold text-slate-500">Memuat aplikasi...</div>;
  }

  if (!isLoggedIn) {
    return <PublicSearchPage onLoggedIn={() => setIsLoggedIn(true)} />;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar page={page} setPage={setPage} result={result} downloadReady={Boolean(downloadPath)} />
      <div className="min-w-0 flex-1 p-6 xl:p-8">
        <div className="mb-4 flex justify-end">
          <button onClick={logout} className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-700 shadow-sm hover:bg-slate-50">
            <LogOut className="h-4 w-4" /> Logout
          </button>
        </div>
        {error && page !== "analisis" ? <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</div> : null}
        {page === "dashboard" && <DashboardPage result={filteredResult} search={search} setSearch={setSearch} setPage={setPage} onGenerate={onGenerate} />}
        {page === "analisis" && <AnalisisPage mode={mode} setMode={setMode} masterFile={masterFile} setMasterFile={setMasterFile} rekapFile={rekapFile} setRekapFile={setRekapFile} useGroq={useGroq} setUseGroq={setUseGroq} onAnalyze={onAnalyze} loading={loading} result={result} error={error} />}
        {page === "validasi-nama" && <ValidasiNamaPage result={result} approvals={approvals} setApprovals={setApprovals} onApply={onApply} />}
        {page === "validasi-nilai" && <ValidasiNilaiPage result={result} />}
        {page === "preview" && <PreviewOutputPage result={result} />}
        {page === "download" && <DownloadPage result={result} generating={generating} downloading={downloading} downloadPath={downloadPath} onGenerate={onGenerate} onDownload={onDownload} />}
      </div>
    </div>
  );
}
