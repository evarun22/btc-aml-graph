from loguru import logger

from ..neo4j_client import session


BATCH_SIZE = 500


SOURCES_QUERY = """
MATCH (s:Address)
WHERE count { (s)-[:SENT]->() } >= $thresh
  AND coalesce(s.btc_spent_actual, 0.0) > 1.0
RETURN s.id AS id
ORDER BY id
LIMIT 500
"""


SINKS_QUERY = """
MATCH (s:Address)
WHERE count { ()-[:SENT]->(s) } >= $thresh
  AND coalesce(s.btc_received_actual, 0.0) > 1.0
RETURN s.id AS id
ORDER BY id
LIMIT 500
"""



def _build_path_query(max_depth: int) -> str:
    return f"""
    MATCH (source:Address {{id: $source_id}}),
          (sink:Address {{id: $sink_id}})
    WHERE source <> sink

    CALL (source, sink) {{
        MATCH p = allShortestPaths((source)-[:SENT*1..{int(max_depth)}]->(sink))
        WITH p
        LIMIT 100
        RETURN collect(p) AS paths
    }}

    WITH source, sink, paths
    WHERE size(paths) >= $k

    RETURN source.id AS origin_wallet,
           sink.id AS destination_wallet,
           size(paths) AS path_count,
           reduce(
               total = 0.0,
               p IN paths |
               total + reduce(
                   amount = 0.0,
                   r IN relationships(p) |
                   amount + coalesce(r.transferred_btc, 0.0)
               )
           ) AS total_btc_moved,
           [p IN paths | [r IN relationships(p) | r.tx_hash]] AS nested_tx_hashes
    """


CREATE_ALERTS_QUERY = """
UNWIND $rows AS row

MERGE (al:Alert {alert_id: 'SMURF_' + row.origin_wallet + '_' + row.destination_wallet})
ON CREATE SET
    al.typology = 'Fan-Out/Fan-In Smurfing',
    al.severity = 'CRITICAL',
    al.status = 'NEW',
    al.detected_at = timestamp()

SET
    al.path_count = row.path_count,
    al.total_btc_moved = row.total_btc_moved,
    al.last_detected_at = timestamp()

WITH al, row

MATCH (origin:Address {id: row.origin_wallet})
MATCH (dest:Address {id: row.destination_wallet})

MERGE (origin)-[:FLAGGED_IN]->(al)
MERGE (dest)-[:FLAGGED_IN]->(al)

WITH al, row

UNWIND row.nested_tx_hashes AS path_hashes
UNWIND path_hashes AS tx_hash
MATCH (t:Tx {hash: tx_hash})-[:INPUT|OUTPUT]->(p:Address)
MERGE (p)-[:FLAGGED_IN]->(al)
"""


def _create_alerts(rows: list[dict]) -> None:
    if not rows:
        return

    with session() as s:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            s.run(CREATE_ALERTS_QUERY, rows=batch)


def detect_and_alert_smurfing_cycles(
    out_degree_thresh: int = 50,
    in_degree_thresh: int = 50,
    required_paths: int = 3,
    max_smurf_depth: int = 6,
    max_pairs: int = 200,
) -> list[dict]:
    """
    Detect fan-out / fan-in smurfing patterns.

    This implementation uses Cypher shortest-path enumeration
    to stay robust and easier to maintain.
    """
    logger.info("Starting smurfing detection...")

    with session() as s:
        sources = [
            record["id"]
            for record in s.run(SOURCES_QUERY, thresh=out_degree_thresh)
        ]
        sinks = [
            record["id"]
            for record in s.run(SINKS_QUERY, thresh=in_degree_thresh)
        ]

    logger.info(f"Found {len(sources)} sources and {len(sinks)} sinks.")

    if not sources or not sinks:
        logger.info("No smurfing candidates found.")
        return []

    path_query = _build_path_query(max_smurf_depth)
    flagged = []

    with session() as s:
        pairs_checked = 0

        for source_id in sources:
            for sink_id in sinks:
                if source_id == sink_id:
                    continue

                if pairs_checked >= max_pairs:
                    break

                try:
                    records = s.run(
                        path_query,
                        source_id=source_id,
                        sink_id=sink_id,
                        k=required_paths,
                    ).data()

                    flagged.extend(records)

                except Exception as exc:
                    logger.warning(
                        f"Smurf path query failed for pair {source_id} -> {sink_id}: {exc}"
                    )

                pairs_checked += 1

            if pairs_checked >= max_pairs:
                break

    if not flagged:
        logger.info("No smurfing cycles detected.")
        return []

    _create_alerts(flagged)
    logger.info(f"Detected {len(flagged)} smurfing patterns and wrote alerts.")

    return flagged
