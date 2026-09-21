export interface GraphNode {
  id: string;
  label: string;
  data: Record<string, any>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  data: Record<string, any>;
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface AddressReport {
  address: string;
  exists: boolean;
  address_type: string | null;
  first_seen: any | null;
  last_seen: any | null;
  btc_received_actual: number | null;
  btc_spent_actual: number | null;
  estimated_balance_btc: number | null;
  in_degree: number;
  out_degree: number;
  entity_id: any | null;
  entity_size: number | null;
  risk_score: number | null;
  risk_level: string | null;
  risk_factors: any[];
  alert_typologies: string[];
  ofac_distance: number | null;
  flags: string[];
  top_senders: Record<string, any>[];
  top_receivers: Record<string, any>[];
  graph: Graph;
}

export interface AlertSummary {
  alert_id: string;
  typology: string | null;
  severity: string | null;
  status: string | null;
  detected_at: any | null;
  risk_score: number | null;
  participant_count: number;
}

export interface AlertDetail {
  alert_id: string;
  typology: string | null;
  severity: string | null;
  status: string | null;
  detected_at: any | null;
  risk_score: number | null;
  properties: Record<string, any>;
  participants: string[];
  tx_hashes: string[];
  entities: any[];
  graph: Graph;
}

export interface EntitySummary {
  entity_id: string;
  address_count: number | null;
  total_received_btc: number | null;
  total_spent_btc: number | null;
  risk_score: number | null;
  risk_level: string | null;
  alert_count: number;
}

export interface EntityDetail {
  entity_id: string;
  properties: Record<string, any>;
  addresses: Record<string, any>[];
  alerts: string[];
  graph: Graph;
}

export interface OfacCheck {
  address: string;
  exists: boolean;
  exact_match: boolean;
  distance: number | null;
  programs: string[];
  names: string[];
  listing_dates: any[];
  exposure_btc: number;
  tx_count: number;
  details: Record<string, any>[];
}

export interface Kpis {
  blocks: number;
  latest_block_height: number | null;
  transactions: number;
  addresses: number;
  entities: number;
  alerts: number;
  critical_alerts: number;
  ofac_sanctioned_loaded: number;
  ofac_1hop: number;
  ofac_2hop: number;
  coinjoin_alerts: number;
  peel_alerts: number;
  smurf_alerts: number;
  volume_at_risk_btc: number | null;
  alerts_by_typology: { typology: string; count: number }[];
}

export interface PipelineStatus {
  last_block_height: number | null;
  updated_at: any | null;
  gds_available: boolean;
  ofac_updated_at: any | null;
  heuristic_version: string | null;
}
