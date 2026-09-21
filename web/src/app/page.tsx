"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

import PageHeader from "@/components/PageHeader";
import KpiCard from "@/components/KpiCard";
import AddressSearchForm from "@/components/AddressSearchForm";
import RiskBadge from "@/components/RiskBadge";
import { getKpis, getPipelineStatus, getAlerts, getEntities } from "@/lib/api";

export default function Home() {
  const [kpis, setKpis] = useState<any>(null);
  const [pipeline, setPipeline] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [entities, setEntities] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.allSettled([
      getKpis(),
      getPipelineStatus(),
      getAlerts({ limit: 8 }),
      getEntities({ limit: 8 }),
    ]).then(([k, p, a, e]) => {
      if (k.status === "fulfilled") setKpis(k.value);
      else setError(k.reason?.message || "Failed to load KPIs");

      if (p.status === "fulfilled") setPipeline(p.value);
      if (a.status === "fulfilled") setAlerts(a.value);
      if (e.status === "fulfilled") setEntities(e.value);
    });
  }, []);

  const chartData = (kpis?.alerts_by_typology || []).map((item: any) => ({
    name: item.typology,
    count: item.count,
  }));

  return (
    <div>
      <PageHeader
        title="Bitcoin AML Graph Intelligence"
        description="Overview of graph ingestion, alerts, entities, and OFAC exposure."
      />

      {error ? (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      <div className="card mb-6">
        <p className="label mb-3">Address Check</p>
        <AddressSearchForm />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard label="Blocks" value={kpis?.blocks ?? 0} />
        <KpiCard label="Latest Block" value={kpis?.latest_block_height ?? "N/A"} />
        <KpiCard label="Transactions" value={kpis?.transactions ?? 0} />
        <KpiCard label="Addresses" value={kpis?.addresses ?? 0} />

        <KpiCard label="Entities" value={kpis?.entities ?? 0} />
        <KpiCard label="Alerts" value={kpis?.alerts ?? 0} tone="warning" />
        <KpiCard
          label="Critical Alerts"
          value={kpis?.critical_alerts ?? 0}
          tone="critical"
        />
        <KpiCard
          label="OFAC Loaded"
          value={kpis?.ofac_sanctioned_loaded ?? 0}
          sub={`1-hop: ${kpis?.ofac_1hop ?? 0} | 2-hop: ${kpis?.ofac_2hop ?? 0}`}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="card lg:col-span-2">
          <p className="label mb-4">Alerts by Typology</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                <YAxis stroke="#94a3b8" fontSize={12} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0f172a", border: "1px solid #334155" }}
                />
                <Bar dataKey="count" fill="#22d3ee" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <p className="label mb-4">Pipeline Status</p>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Last block</span>
              <span>{pipeline?.last_block_height ?? "N/A"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">GDS available</span>
              <span>{pipeline?.gds_available ? "Yes" : "No"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Heuristic version</span>
              <span>{pipeline?.heuristic_version ?? "N/A"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">OFAC updated</span>
              <span>{pipeline?.ofac_updated_at ? new Date(pipeline.ofac_updated_at).toLocaleString() : "N/A"}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <p className="label">Recent Alerts</p>
            <Link href="/alerts" className="text-xs text-cyan-400 hover:text-cyan-300">
              View all
            </Link>
          </div>

          <table className="table">
            <thead>
              <tr>
                <th className="th">Alert</th>
                <th className="th">Typology</th>
                <th className="th">Severity</th>
                <th className="th">Participants</th>
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
                  <td className="td">{alert.participant_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <p className="label">Top Risky Entities</p>
            <Link href="/entities" className="text-xs text-cyan-400 hover:text-cyan-300">
              View all
            </Link>
          </div>

          <table className="table">
            <thead>
              <tr>
                <th className="th">Entity</th>
                <th className="th">Addresses</th>
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
    </div>
  );
}
