"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import PageHeader from "@/components/PageHeader";
import RiskBadge from "@/components/RiskBadge";
import GraphViewer from "@/components/GraphViewer";
import { getAlert } from "@/lib/api";

export default function AlertDetailPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;

  const [alert, setAlert] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    getAlert(String(id))
      .then(setAlert)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-sm text-slate-400">Loading alert...</p>;

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!alert) return null;

  return (
    <div>
      <PageHeader title={alert.alert_id} description={`Typology: ${alert.typology || "N/A"}`} />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <RiskBadge score={alert.risk_score} level={alert.severity} />
        <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
          Status: {alert.status || "N/A"}
        </span>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card">
          <p className="label mb-3">Participants</p>
          <div className="max-h-64 overflow-y-auto">
            {alert.participants?.map((participant: string) => (
              <div key={participant} className="border-b border-slate-800/60 py-2 text-sm">
                {participant}
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <p className="label mb-3">Transaction Hashes</p>
          <div className="max-h-64 overflow-y-auto">
            {alert.tx_hashes?.map((tx: string) => (
              <div key={tx} className="border-b border-slate-800/60 py-2 text-sm">
                {tx}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="card mb-6">
        <p className="label mb-3">Alert Properties</p>
        <pre className="max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-300">
          {JSON.stringify(alert.properties, null, 2)}
        </pre>
      </div>

      <div className="card">
        <p className="label mb-3">Alert Graph</p>
        <GraphViewer graph={alert.graph} height={520} />
      </div>
    </div>
  );
}
