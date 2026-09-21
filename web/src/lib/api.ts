const API_BASE = "/api";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export function buildQuery(params: Record<string, any>) {
  const qs = new URLSearchParams(
    Object.entries(params)
      .filter(([, value]) => value !== undefined && value !== null && value !== "")
      .map(([key, value]) => [key, String(value)])
  ).toString();

  return qs ? `?${qs}` : "";
}

export const getHealth = () => fetchJson<{ status: string; neo4j: boolean }>("/health");

export const getKpis = () => fetchJson<any>("/kpis");

export const getPipelineStatus = () => fetchJson<any>("/pipeline/status");

export const getAddress = (address: string, depth = 1, max_nodes = 120) =>
  fetchJson<any>(
    `/addresses/${encodeURIComponent(address)}${buildQuery({ depth, max_nodes })}`
  );

export const getAlerts = (params: Record<string, any> = {}) =>
  fetchJson<any[]>(`/alerts${buildQuery(params)}`);

export const getAlert = (id: string) =>
  fetchJson<any>(`/alerts/${encodeURIComponent(id)}`);

export const getEntities = (params: Record<string, any> = {}) =>
  fetchJson<any[]>(`/entities${buildQuery(params)}`);

export const getEntity = (id: string) =>
  fetchJson<any>(`/entities/${encodeURIComponent(id)}`);

export const getOfacCheck = (address: string) =>
  fetchJson<any>(`/ofac/check${buildQuery({ address })}`);

export const getOfacExposure = (limit = 50) =>
  fetchJson<any[]>(`/ofac/exposure${buildQuery({ limit })}`);

export const getSubgraph = (address: string, depth = 1, max_nodes = 150) =>
  fetchJson<any>(`/graph/subgraph${buildQuery({ address, depth, max_nodes })}`);
