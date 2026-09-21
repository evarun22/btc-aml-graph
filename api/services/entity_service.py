from typing import Any
from api.neo4j_service import Neo4jService
from api.schemas.models import EntityDetail, EntitySummary, Graph, GraphNode, GraphEdge
from api.services.queries import (
    LIST_ENTITIES_QUERY,
    ENTITY_DETAIL_QUERY,
)


def _coerce_entity_id(entity_id: str) -> Any:
    return int(entity_id) if entity_id.isdigit() else entity_id


class EntityService:
    def __init__(self, neo4j: Neo4jService):
        self.neo4j = neo4j

    def list_entities(
        self,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[EntitySummary]:
        rows = self.neo4j.query(
            LIST_ENTITIES_QUERY,
            {
                "search": search,
                "limit": limit,
                "offset": offset,
            },
        )
        return [EntitySummary(**row) for row in rows]

    def get_entity(self, entity_id: str) -> EntityDetail:
        row = self.neo4j.query_one(
            ENTITY_DETAIL_QUERY,
            {"entity_id": _coerce_entity_id(entity_id)},
        )
        if not row:
            raise KeyError(f"Entity not found: {entity_id}")

        props = dict(row["entity"])
        addresses = row.get("addresses") or []
        alerts = row.get("alerts") or []

        graph = self._build_entity_graph(
            entity_id=entity_id,
            addresses=addresses,
            alerts=alerts,
        )

        return EntityDetail(
            entity_id=entity_id,
            properties=props,
            addresses=addresses,
            alerts=alerts,
            graph=graph,
        )

    def _build_entity_graph(
        self,
        entity_id: str,
        addresses: list[dict[str, Any]],
        alerts: list[str],
    ) -> Graph:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}

        entity_node_id = f"entity_{entity_id}"
        nodes[entity_node_id] = GraphNode(
            id=entity_node_id,
            label="Entity",
            data={"id": entity_id, "label": f"Entity {entity_id}"},
        )

        for addr in addresses:
            node_id = addr.get("id")
            if not node_id:
                continue
            nodes[node_id] = GraphNode(
                id=node_id,
                label="Address",
                data={
                    "id": node_id,
                    "label": f"{node_id[:10]}...",
                    "risk_score": addr.get("risk_score"),
                    "risk_level": addr.get("risk_level"),
                },
            )
            edge_id = f"{node_id}|{entity_node_id}|CONTROLLED_BY"
            edges[edge_id] = GraphEdge(
                id=edge_id,
                source=node_id,
                target=entity_node_id,
                data={"relationship": "CONTROLLED_BY"},
            )

        for alert_id in alerts:
            node_id = f"alert_{alert_id}"
            nodes[node_id] = GraphNode(
                id=node_id,
                label="Alert",
                data={"id": alert_id, "label": alert_id},
            )
            edge_id = f"{entity_node_id}|{node_id}|HAS_RISK_EXPOSURE"
            edges[edge_id] = GraphEdge(
                id=edge_id,
                source=entity_node_id,
                target=node_id,
                data={"relationship": "HAS_RISK_EXPOSURE"},
            )

        return Graph(nodes=list(nodes.values()), edges=list(edges.values()))
