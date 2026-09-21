from typing import Any
from api.neo4j_service import Neo4jService
from api.schemas.models import Graph, GraphNode, GraphEdge
from api.services.queries import (
    GET_ADDRESS_PROPS_QUERY,
    NEIGHBOR_EDGES_QUERY,
    CENTER_ENTITY_QUERY,
    CENTER_ALERTS_QUERY,
)


class GraphService:
    def __init__(self, neo4j: Neo4jService, default_max_nodes: int = 180):
        self.neo4j = neo4j
        self.default_max_nodes = default_max_nodes

    def address_subgraph(
        self,
        address: str,
        depth: int = 1,
        max_nodes: int | None = None,
    ) -> Graph:
        max_nodes = min(max_nodes or self.default_max_nodes, 500)
        depth = min(max(depth, 1), 2)

        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}

        center = self.neo4j.query_one(GET_ADDRESS_PROPS_QUERY, {"ids": [address]})
        if not center:
            return Graph(nodes=[], edges=[])

        self._add_address_node(nodes, center)

        visited = {address}
        frontier = [address]

        for _ in range(depth):
            if not frontier or len(nodes) >= max_nodes:
                break

            edge_rows = self.neo4j.query(
                NEIGHBOR_EDGES_QUERY,
                {"addresses": frontier},
                limit=5000,
            )

            missing: set[str] = set()
            for row in edge_rows:
                x = row.get("x")
                y = row.get("y")
                for node_id in (x, y):
                    if node_id and node_id not in nodes and node_id not in missing:
                        missing.add(node_id)

            if missing:
                props_rows = self.neo4j.query(
                    GET_ADDRESS_PROPS_QUERY,
                    {"ids": list(missing)},
                )
                for p in props_rows:
                    if len(nodes) < max_nodes:
                        self._add_address_node(nodes, p)

            for row in edge_rows:
                x = row.get("x")
                y = row.get("y")
                if not x or not y:
                    continue
                if x not in nodes or y not in nodes:
                    continue

                edge_id = f"{x}|{y}|{row.get('type')}|{row.get('tx_hash')}"
                if edge_id not in edges:
                    edges[edge_id] = GraphEdge(
                        id=edge_id,
                        source=x,
                        target=y,
                        data={
                            "relationship": row.get("type"),
                            "amount": row.get("amount"),
                            "tx_hash": row.get("tx_hash"),
                        },
                    )

            frontier = [node_id for node_id in missing if node_id in nodes]

        # Add entity and alert context for the center address
        for e in self.neo4j.query(CENTER_ENTITY_QUERY, {"address": address}):
            entity_id = e.get("entity_id")
            if entity_id is None:
                continue
            node_id = f"entity_{entity_id}"
            nodes[node_id] = GraphNode(
                id=node_id,
                label="Entity",
                data={
                    "id": entity_id,
                    "label": f"Entity {entity_id}",
                    "address_count": e.get("address_count"),
                    "risk_score": e.get("risk_score"),
                    "risk_level": e.get("risk_level"),
                },
            )
            edge_id = f"{address}|{node_id}|CONTROLLED_BY"
            edges[edge_id] = GraphEdge(
                id=edge_id,
                source=address,
                target=node_id,
                data={"relationship": "CONTROLLED_BY"},
            )

        for al in self.neo4j.query(CENTER_ALERTS_QUERY, {"address": address}):
            alert_id = al.get("alert_id")
            if not alert_id:
                continue
            node_id = f"alert_{alert_id}"
            nodes[node_id] = GraphNode(
                id=node_id,
                label="Alert",
                data={
                    "id": alert_id,
                    "label": alert_id,
                    "typology": al.get("typology"),
                    "severity": al.get("severity"),
                },
            )
            edge_id = f"{address}|{node_id}|FLAGGED_IN"
            edges[edge_id] = GraphEdge(
                id=edge_id,
                source=address,
                target=node_id,
                data={"relationship": "FLAGGED_IN"},
            )

        return Graph(nodes=list(nodes.values()), edges=list(edges.values()))

    def _add_address_node(self, nodes: dict[str, GraphNode], props: dict[str, Any]) -> None:
        node_id = props.get("id")
        if not node_id or node_id in nodes:
            return

        labels = props.get("labels") or []
        is_sanctioned = "SanctionedAddress" in labels

        nodes[node_id] = GraphNode(
            id=node_id,
            label="Address",
            data={
                "id": node_id,
                "label": f"{node_id[:10]}...",
                "risk_score": props.get("risk_score"),
                "risk_level": props.get("risk_level"),
                "ofac_distance": props.get("ofac_distance"),
                "btc_received_actual": props.get("btc_received_actual"),
                "btc_spent_actual": props.get("btc_spent_actual"),
                "is_sanctioned": is_sanctioned,
                "labels": labels,
            },
        )
