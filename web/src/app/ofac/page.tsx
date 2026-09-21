"use client";

import { useEffect, useState } from "react";

import PageHeader from "@/components/PageHeader";
import RiskBadge from "@/components/RiskBadge";
import { getOfacCheck, getOfacExposure } from "@/lib/api";

export default function OfacPage() {
  const [address, setAddress] = useState("");
  const [result, setResult] = useState<any>(null);
  const [exposure, setExposure] = useState<any[]>([]);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    getOfacExposure(50)
      .then(setExposure)
      .catch((err) => setError(err.message));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!address.trim()) return;

    setChecking(true);
    setError("");
    try {
      const data = await getOfacCheck(address.trim());
      setResult(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setChecking(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="OFAC Screen"
        description="Check exact OFAC matches and proximity exposure."
      />

      <div className="card mb-6">
        <form onSubmit={onSubmit} className="flex flex-col gap-3 sm:flex-row">
          <input
            className="input"
            placeholder="Enter BTC address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />
          <button className="btn" type="submit" disabled={checking}>
            {checking ? "Checking..." : "Check OFAC"}
          </button>
        </form>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="mb-6 card">
          <p className="label mb-3">Result</p>

          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span
              className={
                result.exact_match
                  ? "rounded-full border border-red-500/40 bg-red-500/20 px-3 py-1 text-xs text-red-300"
                  : "rounded-full border border-emerald-500/40 bg-emerald-500/20 px-3 py-1 text-xs text-emerald-300"
              }
            >
              {result.exact_match ? "Exact OFAC Match" : "No Exact Match"}
            </span>

            {result.distance !== null && result.distance !== undefined ? (
              <RiskBadge score={null} level={result.distance === 0 ? "CRITICAL" : "HIGH"} />
            ) : null}

            <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
              Distance: {result.distance ?? "None"}
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="label">Exists in Graph</p>
              <p className="mt-1 text-sm">{result.exists ? "Yes" : "No"}</p>
            </div>
            <div>
              <p className="label">Programs</p>
              <p className="mt-1 text-sm">{result.programs?.join(", ") || "N/A"}</p>
            </div>
            <div>
              <p className="label">Exposure</p>
              <p className="mt-1 text-sm">{result.exposure_btc?.toFixed(8)} BTC</p>
            </div>
            <div>
              <p className="label">Tx Count</p>
              <p className="mt-1 text-sm">{result.tx_count}</p>
            </div>
          </div>
        </div>
      ) : null}

      <div className="card">
        <p className="label mb-3">Top OFAC Exposure</p>
        <div className="overflow-x-auto">
          <table className="table">
            <thead>
              <tr>
                <th className="th">Address</th>
                <th className="th">OFAC Distance</th>
                <th className="th">Risk Score</th>
                <th className="th">Received</th>
              </tr>
            </thead>
            <tbody>
              {exposure.map((row) => (
                <tr key={row.address}>
                  <td className="td">{row.address}</td>
                  <td className="td">{row.ofac_distance}</td>
                  <td className="td">{row.risk_score ?? "N/A"}</td>
                  <td className="td">{Number(row.btc_received_actual || 0).toFixed(8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
