import { LucideIcon } from "lucide-react";

export function ActionCard({ title, subtitle, icon: Icon, onClick }: { title: string; subtitle: string; icon: LucideIcon; onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex w-full items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm transition hover:border-blue-300 hover:shadow-soft">
      <div className="rounded-2xl bg-indigo-50 p-3 text-indigo-600"><Icon className="h-5 w-5" /></div>
      <div><p className="font-bold text-slate-800">{title}</p><p className="text-xs text-slate-500">{subtitle}</p></div>
    </button>
  );
}
