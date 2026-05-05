import { Upload } from "lucide-react";

export function UploadCard({ label, file, onChange, required = false }: { label: string; file: File | null; onChange: (file: File | null) => void; required?: boolean }) {
  return (
    <label className="block rounded-2xl border border-dashed border-blue-200 bg-white p-5 shadow-sm transition hover:border-blue-400">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-blue-50 p-3 text-blue-600"><Upload className="h-5 w-5" /></div>
        <div>
          <p className="text-sm font-bold text-slate-800">{label} {required ? <span className="text-red-500">*</span> : null}</p>
          <p className="text-xs text-slate-500">{file ? file.name : "Pilih file .xlsx"}</p>
        </div>
      </div>
      <input className="mt-4 block w-full text-sm" type="file" accept=".xlsx,.xls" onChange={(e) => onChange(e.target.files?.[0] ?? null)} />
    </label>
  );
}
