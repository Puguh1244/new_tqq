import { AlertTriangle, CheckCircle2, Download, Eye, FileCheck2, HelpCircle, Layers, Search, UsersRound, XCircle } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MetricCard } from "@/components/MetricCard";
import { ChartCard } from "@/components/ChartCard";
import { DataTable } from "@/components/DataTable";
import { ActionCard } from "@/components/ActionCard";
import { PageKey } from "@/types";

export function DashboardPage({ result, search, setSearch, setPage, onGenerate }: { result: any; search: string; setSearch: (s: string) => void; setPage: (p: PageKey) => void; onGenerate: () => void }) {
  const s = result?.summary || {};
  const dashboard = result?.dashboard || {};
  const total = s.total_mahasiswa_rekap || 0;

  return (
    <main className="space-y-5">
      <header className="flex items-start justify-between gap-4">
        <div><h2 className="text-3xl font-black tracking-tight text-slate-900">Dashboard Analisis</h2><p className="mt-1 text-sm text-slate-500">Pantau hasil pemetaan, validasi nilai, dan distribusi kelas secara ringkas.</p></div>
        <div className="relative w-80"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari nama mahasiswa..." className="w-full rounded-2xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm outline-none ring-blue-200 focus:ring-4" /></div>
      </header>

      <section className="grid grid-cols-2 gap-3 xl:grid-cols-4 2xl:grid-cols-8">
        <MetricCard title="Total Mahasiswa Rekap" value={total} icon={UsersRound} />
        <MetricCard title="Exact Match" value={s.exact_match ?? 0} hint={total ? `${((s.exact_match || 0) / total * 100).toFixed(1)}%` : "0%"} icon={CheckCircle2} />
        <MetricCard title="Normalized Match" value={s.normalized_match ?? 0} icon={Layers} />
        <MetricCard title="Perlu Konfirmasi" value={s.perlu_konfirmasi ?? 0} icon={HelpCircle} />
        <MetricCard title="Tidak Ditemukan" value={s.tidak_ditemukan ?? 0} icon={XCircle} />
        <MetricCard title="Nilai Mencurigakan" value={s.nilai_mencurigakan ?? 0} icon={AlertTriangle} />
        <MetricCard title="Duplikat" value={s.duplikat ?? 0} icon={FileCheck2} />
        <MetricCard title="Jumlah Kelas" value={s.jumlah_kelas ?? 0} icon={Layers} />
      </section>

      {!result ? <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">Upload file dan jalankan analisis untuk melihat dashboard.</div> : null}

      {result ? <>
        <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <ChartCard title="Distribusi Status Mapping"><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={dashboard.status_distribution || []} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={3}>{(dashboard.status_distribution || []).map((_: any, i: number) => <Cell key={i} />)}</Pie><Tooltip /><Legend /></PieChart></ResponsiveContainer></ChartCard>
          <ChartCard title="Top 10 Kelas Asli"><ResponsiveContainer width="100%" height={240}><BarChart data={dashboard.top_classes || []}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="kode_kelas" /><YAxis /><Tooltip /><Bar dataKey="jumlah_mahasiswa" /></BarChart></ResponsiveContainer></ChartCard>
          <ChartCard title="Ringkasan Validasi Nilai"><ResponsiveContainer width="100%" height={240}><BarChart data={dashboard.score_summary || []} layout="vertical"><CartesianGrid strokeDasharray="3 3" /><XAxis type="number" /><YAxis dataKey="name" type="category" width={120} /><Tooltip /><Bar dataKey="value" /></BarChart></ResponsiveContainer></ChartCard>
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-3">
          <div className="xl:col-span-2"><ChartCard title="Trend Analisis per Sheet Rekap"><ResponsiveContainer width="100%" height={260}><LineChart data={dashboard.trends || []}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="sheet" /><YAxis /><Tooltip /><Legend /><Line dataKey="exact" /><Line dataKey="normalized" /><Line dataKey="perlu_konfirmasi" /><Line dataKey="unmapped" /></LineChart></ResponsiveContainer></ChartCard></div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h3 className="font-black text-slate-800">Insight Cepat</h3><ul className="mt-4 space-y-3 text-sm text-slate-600"><li>Kelas terbanyak: <b>{dashboard.top_classes?.[0]?.kode_kelas || "-"}</b> ({dashboard.top_classes?.[0]?.jumlah_mahasiswa || 0} mahasiswa).</li><li><b>{s.perlu_konfirmasi || 0}</b> nama masih perlu konfirmasi.</li><li><b>{s.nilai_mencurigakan || 0}</b> nilai terdeteksi mencurigakan.</li><li><b>{s.belum_ada_nilai || 0}</b> mahasiswa belum memiliki nilai.</li></ul></div>
        </section>

        <section className="grid grid-cols-1 gap-4 xl:grid-cols-5">
          <div className="xl:col-span-3"><h3 className="mb-3 font-black text-slate-800">Kelas dengan Mahasiswa Terbanyak</h3><DataTable columns={["kode_kelas", "jumlah_mahasiswa", "exact", "perlu_konfirmasi", "suspicious_scores"]} rows={dashboard.top_classes || []} maxRows={5} /></div>
          <div className="grid gap-3 xl:col-span-2"><ActionCard title="Lihat Validasi Nama" subtitle="Periksa duplikat dan penyeragaman nama" icon={UsersRound} onClick={() => setPage("validasi-nama")} /><ActionCard title="Lihat Validasi Nilai" subtitle="Periksa nilai kosong, outlier, dan duplikat" icon={AlertTriangle} onClick={() => setPage("validasi-nilai")} /><ActionCard title="Preview Output" subtitle="Lihat hasil akhir sebelum diunduh" icon={Eye} onClick={() => setPage("preview")} /><ActionCard title="Generate Excel Final" subtitle="Buat file Excel final untuk rekapitulasi" icon={Download} onClick={onGenerate} /></div>
        </section>
      </> : null}
    </main>
  );
}
