export default function RiskBadge({
  score,
  level,
}: {
  score: number | null;
  level: string | null;
}) {
  const normalized = (level || "LOW").toUpperCase();

  const tone =
    normalized === "CRITICAL"
      ? "border-red-500/40 bg-red-500/20 text-red-300"
      : normalized === "HIGH"
        ? "border-orange-500/40 bg-orange-500/20 text-orange-300"
        : normalized === "MEDIUM"
          ? "border-amber-500/40 bg-amber-500/20 text-amber-300"
          : "border-emerald-500/40 bg-emerald-500/20 text-emerald-300";

  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${tone}`}
    >
      Risk: {score ?? "N/A"}
      <span className="opacity-70">{normalized}</span>
    </span>
  );
}
