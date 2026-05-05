import { BarChart3, CheckCircle2, Download, Eye, FileSpreadsheet, Gauge, ShieldCheck } from "lucide-react";
import { PageKey } from "@/types";
import { cn } from "@/lib/utils";
import { StatusBadge } from "./StatusBadge";

const items: { key: PageKey; label: string; icon: any }[] = [
  { key: "dashboard", label: "Dashboard", icon: Gauge },
  { key: "analisis", label: "Analisis", icon: BarChart3 },
  { key: "validasi-nama", label: "Validasi Nama", icon: ShieldCheck },
  { key: "validasi-nilai", label: "Validasi Nilai", icon: CheckCircle2 },
  { key: "preview", label: "Preview Output", icon: Eye },
  { key: "download", label: "Download", icon: Download },
];

export function Sidebar({ page, setPage, result, downloadReady }: { page: PageKey; setPage: (p: PageKey) => void; result: any; downloadReady: boolean }) {
  const summary = result?.summary || {};
  return (
    <aside className="sticky top-0 h-screen w-72 border-r border-slate-200 bg-white/90 p-5 backdrop-blur">
      <div className="mb-6 flex items-center gap-3">
        <div className="rounded-2xl bg-blue-600 p-2 text-white"><FileSpreadsheet className="h-6 w-6" /></div>
        <div><h1 className="text-lg font-black leading-tight">Rekap Nilai</h1><p className="text-xs font-semibold text-blue-600">Per Kelas Asli</p></div>
      </div>

      <nav className="space-y-2">
        {items.map((item) => {
          const Icon = item.icon;
          return <button key={item.key} onClick={() => setPage(item.key)} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition", page === item.key ? "bg-blue-50 text-blue-700 ring-1 ring-blue-200" : "text-slate-600 hover:bg-slate-50")}><Icon className="h-4 w-4" />{item.label}</button>;
        })}
      </nav>

      <div className="mt-7 rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <p className="mb-3 text-xs font-black uppercase tracking-wide text-slate-500">Ringkasan Data</p>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between"><span>Total Mahasiswa</span><b>{summary.total_mahasiswa_rekap ?? 0}</b></div>
          <div className="flex justify-between"><span>Jumlah Kelas</span><b>{summary.jumlah_kelas ?? 0}</b></div>
          <div className="flex justify-between"><span>Total Sheet</span><b>{summary.total_sheet_rekap ?? 0}</b></div>
          <div className="flex justify-between"><span>Download</span><b>{downloadReady ? "Siap" : "Belum"}</b></div>
        </div>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-4">
        <p className="mb-3 text-xs font-black uppercase tracking-wide text-slate-500">Status Proses</p>
        <div className="space-y-2">
          <StatusBadge tone={result ? "success" : "neutral"}>{result ? "Analisis selesai" : "Belum analisis"}</StatusBadge>
          <div><StatusBadge tone={summary.groq?.available ? "info" : "neutral"}>{summary.groq?.available ? "Groq aktif" : "Groq nonaktif"}</StatusBadge></div>
        </div>
      </div>

      <div className="absolute bottom-5 left-5 right-5 text-xs text-slate-400">
        <p>Dibuat oleh @nama_pembuat</p>
        <p className="mt-1">Versi 1.0.0</p>
      </div>
    </aside>
  );
}
