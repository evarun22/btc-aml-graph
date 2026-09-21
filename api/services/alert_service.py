from typing import Any
from api.neo4j_service import Neo4jService
from api.schemas.models import AlertDetail, AlertSummary, Graph, GraphNode, GraphEdge
from api.services.queries import (
    LIST_ALERTS_QUERY,
    ALERT_DETAIL_QUERY,
    GET_ADDRESS_PROPS_QUERY,
)


class AlertService:
    def __init__(self, neo4j: Neo4jService):
        self.neo4j = neo4j

    def list_alerts(
        self,
        typology: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AlertSummary]:
        rows = self.neo4j.query(
            LIST_ALERTS_QUERY,
            {
                "typology": typology,
                "severity": severity,
                "status": status,
                "search": search,
                "limit": limit,
                "offset": offset,
            },
        )
        return [AlertSummary(**row) for row in rows]

    def get_alert(self, alert_id: str) -> AlertDetail:
        row = self.neo4j.query_one(ALERT_DETAIL_QUERY, {"alert_id": alert_id})
        if not row:
            raise KeyError(f"Alert not found: {alert_id}")

        alert_node = row["alert"]
        props = dict(alert_node)

        participants = row.get("participants") or []
        tx_hashes = row.get("tx_hashes") or []
        entities = row.get("entities") or []

        graph = self._build_alert_graph(
            alert_id=alert_id,
            participants=participants,
            tx_hashes=tx_hashes,
            entities=entities,
        )

        return AlertDetail(
            alert_id=alert_id,
            typology=props.get("typology"),
            severity=props.get("severity"),
            status=props.get("status"),
            detected_at=props.get("detected_at"),
            risk_score=props.get("risk_score"),
            properties=props,
            participants=participants,
            tx_hashes=tx_hashes,
            entities=entities,
            graph=graph,
        )

    def _build_alert_graph(
        self,
        alert_id: str,
        participants: list[str],
        tx_hashes: list[str],
        entities: list[Any],
    ) -> Graph:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}

        nodes[alert_id] = GraphNode(
            id=alert_id,
            label="Alert",
            data={"id": alert_id, "label": alert_id},
        )

        if participants:
            props_rows = self.neo4j.query(
                GET_ADDRESS_PROPS_QUERY,
                {"ids": participants},
            )
            for p in props_rows:
                node_id = p.get("id")
                if not node_id:
                    continue
                labels = p.get("labels") or []
                nodes[node_id] = GraphNode(
                    id=node_id,
                    label="Address",
                    data={
                        "id": node_id,
                        "label": f"{node_id[:10]}...",
                        "risk_score": p.get("risk_score"),
                        "risk_level": p.get("risk_level"),
                        "ofac_distance": p.get("ofac_distance"),
                        "is_sanctioned": "SanctionedAddress" in labels,
                    },
                )
                edge_id = f"{alert_id}|{node_id}|FLAGGED_IN"
                edges[edge_id] = GraphEdge(
                    id=edge_id,
                    source=alert_id,
                    target=node_id,
                    data={"relationship": "FLAGGED_IN"},
                )

        for tx in tx_hashes:
            node_id = f"tx_{tx}"
            nodes[node_id] = GraphNode(
                id=node_id,
                label="Tx",
                data={"id": tx, "label": f"{tx[:10]}..."},
            )
            edge_id = f"{alert_id}|{node_id}|ABOUT_TX"
            edges[edge_id] = GraphEdge(
                id=edge_id,
                source=alert_id,
                target=node_id,
                data={"relationship": "ABOUT_TX"},
            )

        for entity in entities:
            node_id = f"entity_{entity}"
            nodes[node_id] = GraphNode(
                id=node_id,
                label="Entity",
                data={"id": entity, "label": f"Entity {entity}"},
            )
            edge_id = f"{node_id}|{alert_id}|HAS_RISK_EXPOSURE"
            edges[edge_id] = GraphEdge(
                id=edge_id,
                source=node_id,
                target=alert_id,
                data={"relationship": "HAS_RISK_EXPOSURE"},
            )

        return Graph(nodes=list(nodes.values()), edges=list(edges.values()))
