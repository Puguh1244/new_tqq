"use client";

import { useState } from "react";
import { FileSpreadsheet, Loader2, LockKeyhole, Search } from "lucide-react";
import { loginAdmin, publicSearchNim } from "@/lib/api";

export function PublicSearchPage({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [nim, setNim] = useState("");
  const [rows, setRows] = useState<Record<string, any>[]>([]);
  const [columns, setColumns] = useState<string[]>(["NIM", "NAMA", "KODE KELAS PAI"]);
  const [message, setMessage] = useState("Masukkan NIM lalu klik Cari.");
  const [searchLoading, setSearchLoading] = useState(false);
  const [loginLoading, setLoginLoading] = useState(false);
  const [showLogin, setShowLogin] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSearch() {
    if (!nim.trim()) return;
    setError(null);
    setSearchLoading(true);
    try {
      const data = await publicSearchNim(nim.trim());
      const nextRows = data.rows || data.results || [];
      setRows(nextRows);
      setColumns(data.columns?.length ? data.columns : nextRows[0] ? Object.keys(nextRows[0]) : ["NIM", "NAMA", "KODE KELAS PAI"]);
      setMessage(data.message || (nextRows.length ? "Data ditemukan." : "Data tidak ditemukan."));
      if (!data.ready) setError(data.message || "Data pencarian belum tersedia. Login admin lalu Generate Excel Final dulu.");
    } catch (e: any) {
      setRows([]);
      setError(e.message || "Gagal mencari NIM.");
    } finally {
      setSearchLoading(false);
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoginLoading(true);
    try {
      await loginAdmin(username, password);
      onLoggedIn();
    } catch (e: any) {
      setError(e.message || "Login gagal.");
    } finally {
      setLoginLoading(false);
    }
  }

  const visibleColumns = rows.length ? Object.keys(rows[0]) : columns;

  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 px-5 py-8">
      <div className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-2xl bg-blue-600 p-3 text-white shadow-sm"><FileSpreadsheet className="h-6 w-6" /></div>
          <div>
            <h1 className="text-xl font-black text-slate-900">Rekap Nilai Per Kelas Asli</h1>
            <p className="text-sm font-medium text-slate-500">Pencarian publik berdasarkan NIM</p>
          </div>
        </div>
        <button onClick={() => setShowLogin((v) => !v)} className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-2.5 text-sm font-bold text-white shadow-sm">
          <LockKeyhole className="h-4 w-4" /> Login Admin
        </button>
      </div>

      <section className="mx-auto mt-10 grid max-w-7xl gap-6 lg:grid-cols-[1.55fr_0.7fr]">
        <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-soft">
          <div className="mb-6">
            <p className="text-sm font-bold uppercase tracking-wide text-blue-600">Cek Data Mahasiswa</p>
            <h2 className="mt-2 text-4xl font-black tracking-tight text-slate-950">Cari nama berdasarkan NIM</h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-500">
              Masukkan NIM untuk melihat data mahasiswa. Kolom yang tampil mengikuti Excel final terakhir yang digenerate admin.
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-3.5 h-5 w-5 text-slate-400" />
              <input
                value={nim}
                onChange={(e) => setNim(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") handleSearch(); }}
                placeholder="Masukkan NIM..."
                className="w-full rounded-2xl border border-slate-200 bg-white py-3 pl-12 pr-4 text-base font-semibold outline-none ring-blue-200 focus:ring-4"
              />
            </div>
            <button onClick={handleSearch} disabled={searchLoading || !nim.trim()} className="inline-flex items-center justify-center gap-2 rounded-2xl bg-blue-600 px-6 py-3 font-bold text-white shadow-sm disabled:opacity-60">
              {searchLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-5 w-5" />} Cari
            </button>
          </div>

          {error ? <div className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700">{error}</div> : null}

          <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white">
            <div className="max-h-[560px] overflow-auto">
              <table className="min-w-max w-full text-sm">
                <thead className="sticky top-0 z-10 bg-slate-50">
                  <tr>{visibleColumns.map((col) => <th key={col} className="whitespace-nowrap border-b px-4 py-3 text-left text-xs font-black uppercase tracking-wide text-slate-500">{col}</th>)}</tr>
                </thead>
                <tbody>
                  {rows.length ? rows.map((row, idx) => (
                    <tr key={idx} className="border-b last:border-b-0">
                      {visibleColumns.map((col) => <td key={col} className="whitespace-nowrap px-4 py-3 font-medium text-slate-700">{String(row[col] ?? "")}</td>)}
                    </tr>
                  )) : (
                    <tr><td colSpan={visibleColumns.length || 3} className="px-4 py-10 text-center text-slate-500">{message}</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <p className="mt-3 text-xs text-slate-400">Data pencarian disimpan di Supabase. Kalau data belum muncul, login admin lalu Analisis ulang dan Generate Excel Final ulang.</p>
        </div>

        <aside className="rounded-3xl border border-slate-200 bg-white p-7 shadow-soft">
          <h3 className="text-xl font-black text-slate-900">Login Admin</h3>
          <p className="mt-2 text-sm leading-6 text-slate-500">Login untuk membuka dashboard analisis, validasi, preview, generate, dan download Excel final.</p>

          {showLogin ? (
            <form onSubmit={handleLogin} className="mt-6 space-y-3">
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username" className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none focus:ring-4 focus:ring-blue-100" />
              <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" placeholder="Password" className="w-full rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none focus:ring-4 focus:ring-blue-100" />
              <button disabled={loginLoading} className="inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-blue-600 px-5 py-3 font-bold text-white disabled:opacity-60">
                {loginLoading ? <Loader2 className="h-5 w-5 animate-spin" /> : <LockKeyhole className="h-5 w-5" />} Masuk
              </button>
            </form>
          ) : (
            <button onClick={() => setShowLogin(true)} className="mt-6 inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-5 py-3 font-bold text-white">
              <LockKeyhole className="h-4 w-4" /> Tampilkan Form Login
            </button>
          )}
        </aside>
      </section>
    </main>
  );
}
