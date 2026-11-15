"use client";

import { useState } from "react";
import { explainAlert } from "@/lib/api";

interface AiExplainButtonProps {
  alertId: string;
}

export default function AiExplainButton({ alertId }: AiExplainButtonProps) {
  const [loading, setLoading] = useState(false);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setError(null);
    setExplanation(null);

    try {
      const data = await explainAlert(alertId);
      setExplanation(data.explanation);
    } catch (err: any) {
      setError(err.message || "AI assistant is unavailable. Please try again later.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-slate-200">
          AI Analyst
        </h3>
        <p className="text-xs text-slate-400">
          Explain this alert in plain English.
        </p>
      </div>

      <button
        onClick={handleClick}
        disabled={loading}
        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Explaining..." : "Explain in plain English"}
      </button>

      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {explanation && (
        <div className="max-h-96 overflow-y-auto rounded-md border border-indigo-500/30 bg-indigo-500/10 p-4 text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
          {explanation}
        </div>
      )}
    </div>
  );
}
