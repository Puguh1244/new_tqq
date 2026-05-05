import { Loader2, PlayCircle } from "lucide-react";
import { Mode } from "@/types";
import { UploadCard } from "@/components/UploadCard";

export function AnalisisPage(props: {
  mode: Mode; setMode: (m: Mode) => void; masterFile: File | null; setMasterFile: (f: File | null) => void; rekapFile: File | null; setRekapFile: (f: File | null) => void; useGroq: boolean; setUseGroq: (v: boolean) => void; onAnalyze: () => void; loading: boolean; result: any; error: string | null;
}) {
  const { mode, setMode, masterFile, setMasterFile, rekapFile, setRekapFile, useGroq, setUseGroq, onAnalyze, loading, result, error } = props;
  return <main className="space-y-5"><header><h2 className="text-3xl font-black text-slate-900">Analisis Data</h2><p className="mt-1 text-sm text-slate-500">Pilih mode proses, upload Excel, lalu jalankan analisis.</p></header>
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-black text-slate-800">Mode Proses</h3><div className="mt-4 grid gap-3 md:grid-cols-2"><button onClick={() => setMode("with_master")} className={`rounded-2xl border p-4 text-left ${mode === "with_master" ? "border-blue-500 bg-blue-50" : "border-slate-200"}`}><b>Pakai Data Master</b><p className="text-sm text-slate-500">Nama rekap dicocokkan ke Data Master, kelas final dari master.</p></button><button onClick={() => setMode("without_master")} className={`rounded-2xl border p-4 text-left ${mode === "without_master" ? "border-blue-500 bg-blue-50" : "border-slate-200"}`}><b>Tanpa Data Master</b><p className="text-sm text-slate-500">Langsung grouping berdasarkan KODE KELAS PAI di rekap.</p></button></div></section>
    <section className="grid gap-4 lg:grid-cols-2">{mode === "with_master" ? <UploadCard label="Upload Data Master" file={masterFile} onChange={setMasterFile} required /> : null}<UploadCard label="Upload Rekapitulasi Nilai" file={rekapFile} onChange={setRekapFile} required /></section>
    {mode === "with_master" ? <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><label className="flex items-center gap-3 text-sm font-semibold"><input type="checkbox" checked={useGroq} onChange={(e) => setUseGroq(e.target.checked)} />Gunakan Groq untuk bantu deteksi typo nama</label><p className="mt-2 text-xs text-slate-500">API key tetap hanya di backend. Jika Groq gagal, sistem lanjut dengan fuzzy lokal.</p></section> : null}
    {error ? <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</div> : null}
    <button disabled={loading} onClick={onAnalyze} className="inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-6 py-3 font-bold text-white shadow-sm disabled:opacity-60">{loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <PlayCircle className="h-5 w-5" />}Analisis Data</button>
    {result ? <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-800"><b>Analisis selesai.</b> Total {result.summary?.total_mahasiswa_rekap || 0} mahasiswa diproses, {result.summary?.jumlah_kelas || 0} kelas ditemukan.</div> : null}
  </main>;
}
