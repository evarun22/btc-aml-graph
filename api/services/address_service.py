import json
from typing import Any
from api.neo4j_service import Neo4jService
from api.schemas.models import AddressReport, Graph
from api.services.graph_service import GraphService
from api.services.queries import (
    ADDRESS_REPORT_QUERY,
    TOP_SENDERS_QUERY,
    TOP_RECEIVERS_QUERY,
)
from api.utils.address_validation import validate_address, derive_flags


def _normalize_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            pass
        return [value]
    if isinstance(value, list):
        return value
    return [value]


class AddressService:
    def __init__(self, neo4j: Neo4jService, max_graph_nodes: int = 180):
        self.neo4j = neo4j
        self.graph_service = GraphService(neo4j, default_max_nodes=max_graph_nodes)

    def get_report(
        self,
        address: str,
        depth: int = 1,
        max_nodes: int = 120,
    ) -> AddressReport:
        address_type = validate_address(address)
        if not address_type:
            raise ValueError("Invalid Bitcoin address format")

        row = self.neo4j.query_one(ADDRESS_REPORT_QUERY, {"address": address})

        if not row:
            empty_graph = Graph(nodes=[], edges=[])
            return AddressReport(
                address=address,
                exists=False,
                address_type=address_type,
                graph=empty_graph,
            )

        risk_factors = _normalize_list(row.get("risk_factors"))
        alert_typologies = _normalize_list(row.get("alert_typologies"))
        labels = row.get("labels") or []
        ofac_distance = row.get("ofac_distance")

        flags = derive_flags(
            labels=labels,
            ofac_distance=ofac_distance,
            alert_typologies=alert_typologies,
            risk_level=row.get("risk_level"),
            out_degree=row.get("out_degree") or 0,
            in_degree=row.get("in_degree") or 0,
        )

        received = float(row.get("btc_received_actual") or 0.0)
        spent = float(row.get("btc_spent_actual") or 0.0)

        top_senders = self.neo4j.query(TOP_SENDERS_QUERY, {"address": address})
        top_receivers = self.neo4j.query(TOP_RECEIVERS_QUERY, {"address": address})

        graph = self.graph_service.address_subgraph(
            address=address,
            depth=depth,
            max_nodes=max_nodes,
        )

        return AddressReport(
            address=address,
            exists=True,
            address_type=address_type,
            first_seen=row.get("first_seen"),
            last_seen=row.get("last_seen"),
            btc_received_actual=received,
            btc_spent_actual=spent,
            estimated_balance_btc=round(received - spent, 8),
            in_degree=int(row.get("in_degree") or 0),
            out_degree=int(row.get("out_degree") or 0),
            entity_id=row.get("entity_id"),
            entity_size=row.get("entity_size"),
            risk_score=row.get("risk_score"),
            risk_level=row.get("risk_level"),
            risk_factors=risk_factors,
            alert_typologies=alert_typologies,
            ofac_distance=ofac_distance,
            flags=flags,
            top_senders=top_senders,
            top_receivers=top_receivers,
            graph=graph,
        )
