import { MetricCard } from "@/components/MetricCard";
import { DataTable } from "@/components/DataTable";
import { AlertTriangle, CircleOff, MinusCircle, PlusCircle } from "lucide-react";

export function ValidasiNilaiPage({ result }: { result: any }) {
  const rows = result?.validation_scores || [];
  const count = (type: string) => rows.filter((r: any) => r.jenis_masalah === type).length;
  return <main className="space-y-5"><header><h2 className="text-3xl font-black text-slate-900">Validasi Nilai</h2><p className="mt-1 text-sm text-slate-500">Nilai tidak diperbaiki otomatis; semua masalah dicatat ke sheet audit.</p></header><section className="grid gap-3 md:grid-cols-4"><MetricCard title="Nilai Kosong" value={count("NILAI_KOSONG")} icon={CircleOff} /><MetricCard title="Nilai > 100" value={rows.filter((r: any) => ["NILAI_LEBIH_DARI_100", "TOTAL_NILAI_MENCURIGAKAN"].includes(r.jenis_masalah)).length} icon={PlusCircle} /><MetricCard title="Nilai < 0" value={count("NILAI_KURANG_DARI_0")} icon={MinusCircle} /><MetricCard title="Total Mencurigakan" value={rows.length} icon={AlertTriangle} /></section><DataTable columns={["sheet_asal", "nama", "kolom_nilai", "nilai", "jenis_masalah", "catatan"]} rows={rows} maxRows={50} /></main>;
}
