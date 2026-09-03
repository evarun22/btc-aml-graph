from loguru import logger

from ..config import get_settings
from ..neo4j_client import session


ADDRESS_RISK_QUERY = """
MATCH (a:Address)

OPTIONAL MATCH (a)-[:FLAGGED_IN]->(al:Alert)

WITH a,
     collect(DISTINCT al.typology) AS alert_typologies,
     min(CASE WHEN al.typology = 'OFAC Exposure' THEN al.ofac_distance ELSE null END) AS ofac_distance,
     exists { (a)-[:FLAGGED_IN]->(:Alert {typology: 'CoinJoin/Mixer'}) } AS coinjoin_flag,
     exists { (a)-[:FLAGGED_IN]->(:Alert {typology: 'Peel Chain'}) } AS peel_flag,
     exists { (a)-[:FLAGGED_IN]->(:Alert {typology: 'Fan-Out/Fan-In Smurfing'}) } AS smurf_flag

OPTIONAL MATCH (a)-[:CONTROLLED_BY]->(e:Entity)

WITH a,
     alert_typologies,
     ofac_distance,
     coinjoin_flag,
     peel_flag,
     smurf_flag,
     e.address_count AS entity_size,
     count { (a)-[:SENT]->() } AS out_degree,
     count { ()-[:SENT]->(a) } AS in_degree

WITH a,
     alert_typologies,
     ofac_distance,
     coinjoin_flag,
     peel_flag,
     smurf_flag,
     entity_size,
     out_degree,
     in_degree,

     CASE
       WHEN ofac_distance = 0 THEN 100
       WHEN ofac_distance = 1 THEN 60
       WHEN ofac_distance = 2 THEN 35
       ELSE 0
     END +

     CASE WHEN coinjoin_flag THEN 20 ELSE 0 END +
     CASE WHEN peel_flag THEN 40 ELSE 0 END +
     CASE WHEN smurf_flag THEN 40 ELSE 0 END +

     CASE WHEN entity_size IS NOT NULL AND entity_size >= 10 THEN 10 ELSE 0 END +
     CASE WHEN out_degree >= 50 THEN 10 ELSE 0 END +
     CASE WHEN in_degree >= 50 THEN 10 ELSE 0 END

     AS raw_score

WITH a,
     alert_typologies,
     ofac_distance,
     coinjoin_flag,
     peel_flag,
     smurf_flag,
     entity_size,
     out_degree,
     in_degree,
     CASE WHEN raw_score > 100 THEN 100 ELSE raw_score END AS score

SET a.risk_score = score,
    a.risk_level = CASE
      WHEN score >= 80 THEN 'CRITICAL'
      WHEN score >= 50 THEN 'HIGH'
      WHEN score >= 25 THEN 'MEDIUM'
      ELSE 'LOW'
    END,
    a.alert_typologies = alert_typologies,
    a.risk_ofac_distance = ofac_distance,
    a.risk_coinjoin = coinjoin_flag,
    a.risk_peel = peel_flag,
    a.risk_smurf = smurf_flag,
    a.risk_entity_size = entity_size,
    a.risk_out_degree = out_degree,
    a.risk_in_degree = in_degree,
    a.risk_factors = reduce(
    factors = [],
    factor IN [
        CASE WHEN ofac_distance IS NOT NULL THEN 'ofac_distance=' + toString(ofac_distance) ELSE null END,
        CASE WHEN coinjoin_flag THEN 'coinjoin' ELSE null END,
        CASE WHEN peel_flag THEN 'peel' ELSE null END,
        CASE WHEN smurf_flag THEN 'smurf' ELSE null END,
        CASE WHEN entity_size IS NOT NULL AND entity_size >= 10 THEN 'large_entity' ELSE null END,
        CASE WHEN out_degree >= 50 THEN 'high_out_degree' ELSE null END,
        CASE WHEN in_degree >= 50 THEN 'high_in_degree' ELSE null END
    ]
    | CASE WHEN factor IS NOT NULL THEN factors + [factor] ELSE factors END
  ),
    a.risk_score_version = $version
"""


ENTITY_RISK_QUERY = """
MATCH (e:Entity)<-[:CONTROLLED_BY]-(a:Address)

WITH e,
     max(coalesce(a.risk_score, 0)) AS max_score,
     avg(coalesce(a.risk_score, 0.0)) AS avg_score,
     count(CASE WHEN coalesce(a.risk_score, 0) >= 50 THEN 1 END) AS high_risk_addresses

SET e.risk_score = max_score,
    e.avg_risk_score = round(avg_score, 2),
    e.high_risk_addresses = high_risk_addresses,
    e.risk_level = CASE
      WHEN max_score >= 80 THEN 'CRITICAL'
      WHEN max_score >= 50 THEN 'HIGH'
      WHEN max_score >= 25 THEN 'MEDIUM'
      ELSE 'LOW'
    END,
    e.risk_score_version = $version
"""


PROPAGATE_RISK_QUERY = """
MATCH (a:Address)-[:FLAGGED_IN]->(al:Alert)
MATCH (a)-[:CONTROLLED_BY]->(e:Entity)
MERGE (e)-[:HAS_RISK_EXPOSURE]->(al)
"""


def compute_risk_scores(version: str | None = None) -> None:
    """
    Compute rule-based risk scores for addresses and entities.
    """
    settings = get_settings()
    version = version or settings.heuristic_version

    logger.info("Computing address risk scores...")

    with session() as s:
        result = s.run(ADDRESS_RISK_QUERY, version=version)
        summary = result.consume()
        logger.info(
            f"Address risk scoring complete. Properties set: {summary.counters.properties_set}"
        )

        logger.info("Computing entity risk scores...")
        s.run(ENTITY_RISK_QUERY, version=version)

        logger.info("Propagating entity risk exposure to alerts...")
        s.run(PROPAGATE_RISK_QUERY)

    logger.info("Risk scoring complete.")
