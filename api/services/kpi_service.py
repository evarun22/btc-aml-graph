from typing import Any
from api.neo4j_service import Neo4jService
from api.schemas.models import Kpis, PipelineStatus


class KpiService:
    def __init__(self, neo4j: Neo4jService):
        self.neo4j = neo4j

    def get_kpis(self) -> Kpis:
        blocks = int(self.neo4j.scalar("MATCH (b:Block) RETURN count(b) AS c") or 0)
        latest_block_height = self.neo4j.scalar("MATCH (b:Block) RETURN max(b.height) AS h")
        transactions = int(self.neo4j.scalar("MATCH (t:Tx) RETURN count(t) AS c") or 0)
        addresses = int(self.neo4j.scalar("MATCH (a:Address) RETURN count(a) AS c") or 0)
        entities = int(self.neo4j.scalar("MATCH (e:Entity) RETURN count(e) AS c") or 0)
        alerts = int(self.neo4j.scalar("MATCH (al:Alert) RETURN count(al) AS c") or 0)
        critical_alerts = int(
            self.neo4j.scalar("MATCH (al:Alert) WHERE al.severity = 'CRITICAL' RETURN count(al) AS c") or 0
        )

        ofac_sanctioned_loaded = int(
            self.neo4j.scalar("MATCH (s:Address:SanctionedAddress) RETURN count(s) AS c") or 0
        )
        ofac_1hop = int(
            self.neo4j.scalar("MATCH (a:Address) WHERE a.ofac_distance = 1 RETURN count(a) AS c") or 0
        )
        ofac_2hop = int(
            self.neo4j.scalar("MATCH (a:Address) WHERE a.ofac_distance = 2 RETURN count(a) AS c") or 0
        )

        coinjoin_alerts = int(
            self.neo4j.scalar(
                "MATCH (al:Alert) WHERE toLower(al.typology) CONTAINS 'coinjoin' RETURN count(al) AS c"
            ) or 0
        )
        peel_alerts = int(
            self.neo4j.scalar(
                "MATCH (al:Alert) WHERE toLower(al.typology) CONTAINS 'peel' RETURN count(al) AS c"
            ) or 0
        )
        smurf_alerts = int(
            self.neo4j.scalar(
                "MATCH (al:Alert) WHERE toLower(al.typology) CONTAINS 'smurf' RETURN count(al) AS c"
            ) or 0
        )

        volume_at_risk_btc = self.neo4j.scalar(
            """
            MATCH (a:Address)
            WHERE a.risk_level IN ['HIGH', 'CRITICAL'] OR a.ofac_distance IS NOT NULL
            RETURN sum(coalesce(a.btc_received_actual, 0)) AS v
            """
        )

        alerts_by_typology = self.neo4j.query(
            """
            MATCH (al:Alert)
            RETURN al.typology AS typology, count(*) AS count
            ORDER BY count DESC
            """
        )

        return Kpis(
            blocks=blocks,
            latest_block_height=latest_block_height,
            transactions=transactions,
            addresses=addresses,
            entities=entities,
            alerts=alerts,
            critical_alerts=critical_alerts,
            ofac_sanctioned_loaded=ofac_sanctioned_loaded,
            ofac_1hop=ofac_1hop,
            ofac_2hop=ofac_2hop,
            coinjoin_alerts=coinjoin_alerts,
            peel_alerts=peel_alerts,
            smurf_alerts=smurf_alerts,
            volume_at_risk_btc=volume_at_risk_btc,
            alerts_by_typology=alerts_by_typology,
        )

    def get_pipeline_status(self) -> PipelineStatus:
        state = self.neo4j.query_one(
            """
            MATCH (s:PipelineState {name: 'btc_main'})
            RETURN s.last_block_height AS last_block_height,
                   s.updated_at AS updated_at
            """
        )

        ofac_updated_at = self.neo4j.scalar(
            "MATCH (s:Address:SanctionedAddress) RETURN max(s.updated_at) AS t"
        )

        heuristic_row = self.neo4j.query_one(
            """
            MATCH (t:Tx)
            WHERE t.heuristic_version IS NOT NULL
            RETURN t.heuristic_version AS v
            LIMIT 1
            """
        )

        return PipelineStatus(
            last_block_height=state.get("last_block_height") if state else None,
            updated_at=state.get("updated_at") if state else None,
            gds_available=self.neo4j.gds_available(),
            ofac_updated_at=ofac_updated_at,
            heuristic_version=heuristic_row.get("v") if heuristic_row else None,
        )
