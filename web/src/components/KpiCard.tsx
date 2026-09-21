export default function KpiCard({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string | number;
  sub?: string;
  tone?: "default" | "critical" | "warning" | "success";
}) {
  const toneClass =
    tone === "critical"
      ? "text-red-400"
      : tone === "warning"
        ? "text-amber-400"
        : tone === "success"
          ? "text-emerald-400"
          : "text-slate-100";

  return (
    <div className="card">
      <p className="label">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${toneClass}`}>{value}</p>
      {sub ? <p className="mt-1 text-xs text-slate-500">{sub}</p> : null}
    </div>
  );
}
