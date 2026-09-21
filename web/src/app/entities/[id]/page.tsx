"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import PageHeader from "@/components/PageHeader";
import RiskBadge from "@/components/RiskBadge";
import GraphViewer from "@/components/GraphViewer";
import { getEntity } from "@/lib/api";

export default function EntityDetailPage() {
  const params = useParams();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;

  const [entity, setEntity] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;

    setLoading(true);
    getEntity(String(id))
      .then(setEntity)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <p className="text-sm text-slate-400">Loading entity...</p>;
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-300">
        {error}
      </div>
    );
  }

  if (!entity) {
    return null;
  }

  return (
    <div>
      <PageHeader
        title={`Entity ${entity.entity_id}`}
        description="Entity detail and member addresses"
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <RiskBadge
          score={entity.properties?.risk_score}
          level={entity.properties?.risk_level}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="card">
          <p className="label">Address Count</p>
          <p className="mt-2 text-2xl font-semibold">
            {entity.properties?.address_count ?? "N/A"}
          </p>
        </div>

        <div className="card">
          <p className="label">Total Received</p>
          <p className="mt-2 text-2xl font-semibold">
            {Number(entity.properties?.total_received_btc || 0).toFixed(4)}
          </p>
        </div>

        <div className="card">
          <p className="label">Total Spent</p>
          <p className="mt-2 text-2xl font-semibold">
            {Number(entity.properties?.total_spent_btc || 0).toFixed(4)}
          </p>
        </div>

        <div className="card">
          <p className="label">Alerts</p>
          <p className="mt-2 text-2xl font-semibold">
            {entity.alerts?.length ?? 0}
          </p>
        </div>
      </div>

      <div className="card mb-6">
        <p className="label mb-3">Member Addresses</p>
        <div className="max-h-80 overflow-y-auto">
          <table className="table">
            <thead>
              <tr>
                <th className="th">Address</th>
                <th className="th">Risk Score</th>
                <th className="th">Risk Level</th>
                <th className="th">Received</th>
                <th className="th">Spent</th>
              </tr>
            </thead>
            <tbody>
              {entity.addresses?.map((addr: any) => (
                <tr key={addr.id}>
                  <td className="td">{addr.id}</td>
                  <td className="td">{addr.risk_score ?? "N/A"}</td>
                  <td className="td">{addr.risk_level ?? "N/A"}</td>
                  <td className="td">
                    {Number(addr.btc_received_actual || 0).toFixed(8)}
                  </td>
                  <td className="td">
                    {Number(addr.btc_spent_actual || 0).toFixed(8)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <p className="label mb-3">Entity Graph</p>
        <GraphViewer graph={entity.graph} height={520} />
      </div>
    </div>
  );
}
