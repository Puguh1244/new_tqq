import { cn } from "@/lib/utils";

const toneMap: Record<string, string> = {
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warning: "bg-orange-50 text-orange-700 ring-orange-200",
  error: "bg-red-50 text-red-700 ring-red-200",
  info: "bg-blue-50 text-blue-700 ring-blue-200",
  neutral: "bg-slate-50 text-slate-700 ring-slate-200",
};

export function StatusBadge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: keyof typeof toneMap }) {
  return <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ring-1", toneMap[tone])}>{children}</span>;
}
