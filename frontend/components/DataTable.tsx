export function DataTable({ columns, rows, maxRows = 10 }: { columns: string[]; rows: Record<string, any>[]; maxRows?: number }) {
  const visible = rows.slice(0, maxRows);
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>{columns.map((c) => <th key={c} className="whitespace-nowrap px-4 py-3 text-left text-xs font-bold uppercase tracking-wide text-slate-500">{c.replaceAll("_", " ")}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visible.length ? visible.map((row, idx) => (
              <tr key={idx} className="hover:bg-slate-50">
                {columns.map((c) => <td key={c} className="max-w-[320px] truncate px-4 py-3 text-slate-700">{String(row[c] ?? "")}</td>)}
              </tr>
            )) : (
              <tr><td className="px-4 py-8 text-center text-slate-500" colSpan={columns.length}>Belum ada data.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
