"use client";

import { useEffect, useState } from "react";
import { getAIStatus } from "@/lib/api";
import type { AIStatus } from "@/lib/types";

export default function AiStatusBadge() {
  const [status, setStatus] = useState<AIStatus | null>(null);

  useEffect(() => {
    getAIStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status) {
    return (
      <span className="rounded-full border border-slate-600 px-2 py-1 text-xs text-slate-400">
        AI Unknown
      </span>
    );
  }

  if (!status.available) {
    return (
      <span className="rounded-full border border-red-500/40 bg-red-500/10 px-2 py-1 text-xs text-red-300">
        AI Offline
      </span>
    );
  }

  return (
    <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">
      AI Online
    </span>
  );
}
