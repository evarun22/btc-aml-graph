from typing import Any, Optional
from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    data: dict[str, Any] = {}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    data: dict[str, Any] = {}


class Graph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class AddressReport(BaseModel):
    address: str
    exists: bool
    address_type: Optional[str] = None

    first_seen: Optional[Any] = None
    last_seen: Optional[Any] = None

    btc_received_actual: Optional[float] = None
    btc_spent_actual: Optional[float] = None
    estimated_balance_btc: Optional[float] = None

    in_degree: int = 0
    out_degree: int = 0

    entity_id: Optional[Any] = None
    entity_size: Optional[int] = None

    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    risk_factors: list[Any] = []
    alert_typologies: list[str] = []

    ofac_distance: Optional[int] = None
    flags: list[str] = []

    top_senders: list[dict[str, Any]] = []
    top_receivers: list[dict[str, Any]] = []

    graph: Graph


class AlertSummary(BaseModel):
    alert_id: str
    typology: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    detected_at: Optional[Any] = None
    risk_score: Optional[float] = None
    participant_count: int = 0


class AlertDetail(BaseModel):
    alert_id: str
    typology: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    detected_at: Optional[Any] = None
    risk_score: Optional[float] = None
    properties: dict[str, Any] = {}
    participants: list[str] = []
    tx_hashes: list[str] = []
    entities: list[Any] = []
    graph: Graph


class EntitySummary(BaseModel):
    entity_id: str
    address_count: Optional[int] = None
    total_received_btc: Optional[float] = None
    total_spent_btc: Optional[float] = None
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    alert_count: int = 0


class EntityDetail(BaseModel):
    entity_id: str
    properties: dict[str, Any] = {}
    addresses: list[dict[str, Any]] = []
    alerts: list[str] = []
    graph: Graph


class OfacCheck(BaseModel):
    address: str
    exists: bool
    exact_match: bool
    distance: Optional[int] = None
    programs: list[str] = []
    names: list[str] = []
    listing_dates: list[Any] = []
    exposure_btc: float = 0.0
    tx_count: int = 0
    details: list[dict[str, Any]] = []


class Kpis(BaseModel):
    blocks: int = 0
    latest_block_height: Optional[int] = None
    transactions: int = 0
    addresses: int = 0
    entities: int = 0
    alerts: int = 0
    critical_alerts: int = 0
    ofac_sanctioned_loaded: int = 0
    ofac_1hop: int = 0
    ofac_2hop: int = 0
    coinjoin_alerts: int = 0
    peel_alerts: int = 0
    smurf_alerts: int = 0
    volume_at_risk_btc: Optional[float] = None
    alerts_by_typology: list[dict[str, Any]] = []


class PipelineStatus(BaseModel):
    last_block_height: Optional[int] = None
    updated_at: Optional[Any] = None
    gds_available: bool = False
    ofac_updated_at: Optional[Any] = None
    heuristic_version: Optional[str] = None
