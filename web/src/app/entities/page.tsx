"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import PageHeader from "@/components/PageHeader";
import RiskBadge from "@/components/RiskBadge";
import { getEntities } from "@/lib/api";

export default function EntitiesPage() {
  const [entities, setEntities] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    getEntities({ search, limit: 100 })
      .then(setEntities)
      .catch((err) => setError(err.message));
  }, [search]);

  return (
    <div>
      <PageHeader title="Entity Explorer" description="Browse entities resolved from the graph." />

      {error ? (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      <div className="card mb-4">
        <input
          className="input"
          placeholder="Search entity ID"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="th">Entity</th>
              <th className="th">Addresses</th>
              <th className="th">Received</th>
              <th className="th">Spent</th>
              <th className="th">Risk</th>
              <th className="th">Alerts</th>
            </tr>
          </thead>
          <tbody>
            {entities.map((entity) => (
              <tr key={entity.entity_id}>
                <td className="td">
                  <Link
                    href={`/entities/${entity.entity_id}`}
                    className="text-cyan-400 hover:text-cyan-300"
                  >
                    {entity.entity_id}
                  </Link>
                </td>
                <td className="td">{entity.address_count}</td>
                <td className="td">{Number(entity.total_received_btc || 0).toFixed(4)}</td>
                <td className="td">{Number(entity.total_spent_btc || 0).toFixed(4)}</td>
                <td className="td">
                  <RiskBadge score={entity.risk_score} level={entity.risk_level} />
                </td>
                <td className="td">{entity.alert_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
