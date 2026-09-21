"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import RiskBadge from "@/components/RiskBadge";
import GraphViewer from "@/components/GraphViewer";
import { getAddress } from "@/lib/api";

export default function AddressDetailPage() {
  const params = useParams();
  const address = Array.isArray(params.address) ? params.address[0] : params.address;

  const [report, setReport] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!address) return;

    setLoading(true);
    getAddress(String(address))
      .then((data) => setReport(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [address]);

  if (loading) {
    return <p className="text-sm text-slate-400">Loading address report...</p>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!report) return null;

  return (
    <div>
      <PageHeader
        title={report.address}
        description={
          report.exists
            ? "Address found in graph"
            : "Address not found in graph"
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <RiskBadge score={report.risk_score} level={report.risk_level} />
        {report.flags?.map((flag: string) => (
          <span
            key={flag}
            className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300"
          >
            {flag}
          </span>
        ))}
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label="Received"
          value={report.btc_received_actual?.toFixed(8) ?? "0.0"}
          sub="BTC actual"
        />
        <KpiCard
          label="Spent"
          value={report.btc_spent_actual?.toFixed(8) ?? "0.0"}
          sub="BTC actual"
        />
        <KpiCard
          label="Est. Balance"
          value={report.estimated_balance_btc?.toFixed(8) ?? "0.0"}
          sub="BTC"
        />
        <KpiCard
          label="OFAC Distance"
          value={report.ofac_distance ?? "None"}
          tone={report.ofac_distance === 0 ? "critical" : "default"}
        />

        <KpiCard label="Entity ID" value={report.entity_id ?? "N/A"} />
        <KpiCard label="Entity Size" value={report.entity_size ?? "N/A"} />
        <KpiCard label="In-degree" value={report.in_degree} />
        <KpiCard label="Out-degree" value={report.out_degree} />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card">
          <p className="label mb-3">Top Senders</p>
          <table className="table">
            <thead>
              <tr>
                <th className="th">Counterparty</th>
                <th className="th">BTC</th>
                <th className="th">Tx Count</th>
              </tr>
            </thead>
            <tbody>
              {report.top_senders?.map((row: any) => (
                <tr key={row.counterparty}>
                  <td className="td">{row.counterparty}</td>
                  <td className="td">{Number(row.btc || 0).toFixed(8)}</td>
                  <td className="td">{row.tx_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <p className="label mb-3">Top Receivers</p>
          <table className="table">
            <thead>
              <tr>
                <th className="th">Counterparty</th>
                <th className="th">BTC</th>
                <th className="th">Tx Count</th>
              </tr>
            </thead>
            <tbody>
              {report.top_receivers?.map((row: any) => (
                <tr key={row.counterparty}>
                  <td className="td">{row.counterparty}</td>
                  <td className="td">{Number(row.btc || 0).toFixed(8)}</td>
                  <td className="td">{row.tx_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <p className="label mb-3">Graph Neighborhood</p>
        <GraphViewer graph={report.graph} height={520} />
      </div>
    </div>
  );
}
