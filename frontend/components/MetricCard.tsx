import { LucideIcon } from "lucide-react";

export function MetricCard({ title, value, hint, icon: Icon }: { title: string; value: React.ReactNode; hint?: string; icon: LucideIcon }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-3">
        <div className="rounded-2xl bg-blue-50 p-3 text-blue-600"><Icon className="h-5 w-5" /></div>
        <div>
          <p className="text-xs font-semibold text-slate-500">{title}</p>
          <p className="text-2xl font-bold tracking-tight text-slate-900">{value}</p>
        </div>
      </div>
      {hint ? <p className="mt-2 text-xs font-medium text-slate-500">{hint}</p> : null}
    </div>
  );
}
