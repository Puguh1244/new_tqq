"use client";

import { useEffect, useMemo, useState } from "react";
import { FileSpreadsheet, Search } from "lucide-react";

function getColumns(sheet: any) {
  if (sheet?.columns?.length) return sheet.columns as string[];
  const first = sheet?.preview_rows?.[0];
  return first ? Object.keys(first) : [];
}

function ExcelLikeTable({ sheet, search }: { sheet: any; search: string }) {
  const columns = getColumns(sheet);
  const rows = (sheet?.preview_rows || []).filter((row: Record<string, any>) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return Object.values(row).some((value) => String(value ?? "").toLowerCase().includes(q));
  });

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div>
          <p className="text-sm font-black text-slate-800">{sheet?.sheet || "Pilih sheet"}</p>
          <p className="text-xs text-slate-500">
            Menampilkan {rows.length} baris preview dari total {sheet?.rows || 0} baris. Semua kolom bisa dicek dengan scroll horizontal.
          </p>
        </div>
      </div>

      <div className="max-h-[560px] overflow-auto">
        <table className="min-w-max border-separate border-spacing-0 text-sm">
          <thead className="sticky top-0 z-10 bg-white shadow-sm">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  className="whitespace-nowrap border-b border-r border-slate-200 bg-slate-50 px-4 py-3 text-left text-xs font-black uppercase tracking-wide text-slate-500"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row: Record<string, any>, index: number) => (
                <tr key={index} className="hover:bg-blue-50/40">
                  {columns.map((column) => (
                    <td
                      key={column}
                      className="whitespace-nowrap border-b border-r border-slate-100 px-4 py-3 text-slate-700"
                    >
                      {String(row[column] ?? "")}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} className="px-4 py-10 text-center text-slate-500">
                  Tidak ada data untuk ditampilkan.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function PreviewOutputPage({ result }: { result: any }) {
  const classSheets = result?.preview?.class_sheets || [];
  const auditSheets = result?.preview?.audit_sheets || [];
  const allSheets = useMemo(() => [...classSheets, ...auditSheets], [classSheets, auditSheets]);
  const [activeSheet, setActiveSheet] = useState<string>("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!activeSheet && allSheets.length) setActiveSheet(allSheets[0].sheet);
    if (activeSheet && allSheets.length && !allSheets.some((sheet: any) => sheet.sheet === activeSheet)) {
      setActiveSheet(allSheets[0].sheet);
    }
  }, [activeSheet, allSheets]);

  if (!result) {
    return (
      <main className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-slate-500">
        Jalankan analisis terlebih dahulu.
      </main>
    );
  }

  const selectedSheet = allSheets.find((sheet: any) => sheet.sheet === activeSheet) || allSheets[0];

  return (
    <main className="space-y-5">
      <header className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h2 className="text-3xl font-black text-slate-900">Preview Output</h2>
          <p className="mt-1 text-sm text-slate-500">
            Preview dibuat seperti workbook Excel: pilih sheet kelas atau audit, lalu cek isi tabelnya sebelum download.
          </p>
        </div>
        <div className="relative w-full xl:w-96">
          <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari di sheet aktif..."
            className="w-full rounded-2xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm outline-none ring-blue-200 focus:ring-4"
          />
        </div>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex items-center gap-2 text-sm font-black text-slate-800">
          <FileSpreadsheet className="h-4 w-4 text-blue-600" />
          Sheet Kelas Final
        </div>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {classSheets.map((sheet: any) => (
            <button
              key={sheet.sheet}
              onClick={() => setActiveSheet(sheet.sheet)}
              className={`shrink-0 rounded-xl border px-3 py-2 text-sm font-bold transition ${
                activeSheet === sheet.sheet
                  ? "border-blue-500 bg-blue-50 text-blue-700"
                  : "border-slate-200 bg-white text-slate-600 hover:border-blue-300"
              }`}
            >
              {sheet.sheet}
              <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{sheet.rows}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="mb-3 text-sm font-black text-slate-800">Sheet Audit</div>
        <div className="flex gap-2 overflow-x-auto pb-2">
          {auditSheets.map((sheet: any) => (
            <button
              key={sheet.sheet}
              onClick={() => setActiveSheet(sheet.sheet)}
              className={`shrink-0 rounded-xl border px-3 py-2 text-sm font-bold transition ${
                activeSheet === sheet.sheet
                  ? "border-violet-500 bg-violet-50 text-violet-700"
                  : "border-slate-200 bg-white text-slate-600 hover:border-violet-300"
              }`}
            >
              {sheet.sheet}
              <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{sheet.rows}</span>
            </button>
          ))}
        </div>
      </section>

      <ExcelLikeTable sheet={selectedSheet} search={search} />
    </main>
  );
}
