"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import PageHeader from "@/components/PageHeader";
import RiskBadge from "@/components/RiskBadge";
import { getAlerts } from "@/lib/api";

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<any[]>([]);
  const [filters, setFilters] = useState({
    typology: "",
    severity: "",
    status: "",
    search: "",
  });
  const [error, setError] = useState("");

  useEffect(() => {
    getAlerts({ ...filters, limit: 100 })
      .then(setAlerts)
      .catch((err) => setError(err.message));
  }, [filters]);

  return (
    <div>
      <PageHeader title="Alert Explorer" description="Browse detected AML typologies." />

      {error ? (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      <div className="card mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <input
          className="input"
          placeholder="Typology"
          value={filters.typology}
          onChange={(e) => setFilters({ ...filters, typology: e.target.value })}
        />
        <input
          className="input"
          placeholder="Severity"
          value={filters.severity}
          onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
        />
        <input
          className="input"
          placeholder="Status"
          value={filters.status}
          onChange={(e) => setFilters({ ...filters, status: e.target.value })}
        />
        <input
          className="input"
          placeholder="Search alert ID / typology"
          value={filters.search}
          onChange={(e) => setFilters({ ...filters, search: e.target.value })}
        />
      </div>

      <div className="card overflow-x-auto">
        <table className="table">
          <thead>
            <tr>
              <th className="th">Alert ID</th>
              <th className="th">Typology</th>
              <th className="th">Severity</th>
              <th className="th">Status</th>
              <th className="th">Risk</th>
              <th className="th">Participants</th>
              <th className="th">Detected At</th>
            </tr>
          </thead>
          <tbody>
            {alerts.map((alert) => (
              <tr key={alert.alert_id}>
                <td className="td">
                  <Link
                    href={`/alerts/${alert.alert_id}`}
                    className="text-cyan-400 hover:text-cyan-300"
                  >
                    {alert.alert_id}
                  </Link>
                </td>
                <td className="td">{alert.typology}</td>
                <td className="td">{alert.severity}</td>
                <td className="td">{alert.status}</td>
                <td className="td">
                  <RiskBadge score={alert.risk_score} level={alert.severity} />
                </td>
                <td className="td">{alert.participant_count}</td>
                <td className="td">
                  {alert.detected_at ? new Date(alert.detected_at).toLocaleString() : "N/A"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
