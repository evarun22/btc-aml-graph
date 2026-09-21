"use client";

import { useState } from "react";

import PageHeader from "@/components/PageHeader";
import GraphViewer from "@/components/GraphViewer";
import { getSubgraph } from "@/lib/api";

export default function GraphPage() {
  const [address, setAddress] = useState("");
  const [depth, setDepth] = useState(1);
  const [maxNodes, setMaxNodes] = useState(150);
  const [graph, setGraph] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!address.trim()) return;

    setLoading(true);
    setError("");
    try {
      const data = await getSubgraph(address.trim(), depth, maxNodes);
      setGraph(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="Graph Explorer"
        description="Explore address neighborhoods in the transaction graph."
      />

      <div className="card mb-6">
        <form onSubmit={onSubmit} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <input
            className="input sm:col-span-2"
            placeholder="Enter BTC address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
          />

          <select
            className="input"
            value={depth}
            onChange={(e) => setDepth(Number(e.target.value))}
          >
            <option value={1}>Depth 1</option>
            <option value={2}>Depth 2</option>
          </select>

          <button className="btn" type="submit" disabled={loading}>
            {loading ? "Loading..." : "Explore"}
          </button>
        </form>
      </div>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
          {error}
        </div>
      ) : null}

      <div className="card">
        <p className="label mb-3">Graph</p>
        {graph ? (
          <GraphViewer graph={graph} height={600} />
        ) : (
          <div className="flex h-64 items-center justify-center text-sm text-slate-500">
            Enter an address to explore the graph
          </div>
        )}
      </div>
    </div>
  );
}
