"use client";

import { useState } from "react";
import { summarizeAddress } from "@/lib/api";

interface AiSummaryProps {
  address: string;
}

export default function AiSummary({ address }: AiSummaryProps) {
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleClick() {
    setLoading(true);
    setError(null);
    setSummary(null);

    try {
      const data = await summarizeAddress(address);
      setSummary(data.summary);
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
          AI Risk Summary
        </h3>
        <p className="text-xs text-slate-400">
          Generate a plain-English risk narrative for this address.
        </p>
      </div>

      <button
        onClick={handleClick}
        disabled={loading}
        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Summarizing..." : "Generate AI Risk Summary"}
      </button>

      {error && (
        <div className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {summary && (
        <div className="max-h-96 overflow-y-auto rounded-md border border-indigo-500/30 bg-indigo-500/10 p-4 text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
          {summary}
        </div>
      )}
    </div>
  );
}
