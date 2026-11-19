from loguru import logger

from ..neo4j_client import session


BATCH_SIZE = 1000


ANCHORS_QUERY = """
MATCH (start:Address)-[r:SENT]->(second:Address)
WHERE r.transferred_btc >= $min_btc
  AND NOT r.tx_hash IN $mixer_hashes

RETURN start.id AS origin,
       second.id AS current_node,
       r.transferred_btc AS vol,
       r.tx_hash AS tx_hash
ORDER BY r.transferred_btc DESC
LIMIT $max_anchors
"""



HOP_QUERY = """
UNWIND $batch AS chain

MATCH (current:Address {id: chain.current_node})

WHERE COUNT { (current)-[:SENT]->() } < $max_out_degree

MATCH (current)-[r:SENT]->(next:Address)
WHERE r.transferred_btc <= (chain.current_vol - $min_peel)
  AND r.transferred_btc >= (chain.current_vol * 0.40)

RETURN chain.chain_id AS chain_id,
       next.id AS next_node,
       r.transferred_btc AS next_vol,
       r.tx_hash AS tx_hash
"""


CREATE_ALERTS_QUERY = """
UNWIND $rows AS row

MERGE (al:Alert {alert_id: 'PEEL_' + row.associated_tx_hashes[0]})
ON CREATE SET
    al.typology = 'Peel Chain',
    al.severity = 'CRITICAL',
    al.status = 'NEW',
    al.detected_at = timestamp()

SET
    al.chain_length = row.chain_length,
    al.starting_volume = row.starting_volume,
    al.ending_volume = row.ending_volume,
    al.tx_hashes = row.associated_tx_hashes,
    al.last_detected_at = timestamp()

WITH al, row

MATCH (origin:Address {id: row.origin_wallet})
MATCH (dest:Address {id: row.destination_wallet})

MERGE (origin)-[:FLAGGED_IN]->(al)
MERGE (dest)-[:FLAGGED_IN]->(al)

WITH al, row

UNWIND row.associated_tx_hashes AS tx_hash
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


def detect_and_alert_peel_chains(
    min_starting_btc: float = 1.0,
    min_hops: int = 4,
    max_hops: int = 14,
    min_peel_amount: float = 0.05,
    max_out_degree: int = 500,
    max_active_chains: int = 5000,
) -> list[dict]:
    """
    Detect peel chains using batched BFS over SENT edges.
    """
    logger.info("Starting peel chain detection...")

    with session() as s:
        mixer_hashes = [
            record["tx_hash"]
            for record in s.run(
                """
                MATCH (al:Alert {typology: 'CoinJoin/Mixer'})
                RETURN al.tx_hash AS tx_hash
                """
            )
            if record["tx_hash"]
        ]

        anchors = s.run(
            ANCHORS_QUERY,
            min_btc=min_starting_btc,
            mixer_hashes=mixer_hashes,
            max_anchors=max_active_chains,
        ).data()


    if not anchors:
        logger.info("No peel chain anchors found.")
        return []

    logger.info(f"Found {len(anchors)} peel chain anchors.")

    active_chains = {}

    for i, anchor in enumerate(anchors[:max_active_chains]):
        active_chains[str(i)] = {
            "origin_wallet": anchor["origin"],
            "current_node": anchor["current_node"],
            "start_vol": anchor["vol"],
            "current_vol": anchor["vol"],
            "hashes": [anchor["tx_hash"]],
            "hop_count": 1,
        }

    completed_chains = []
    current_depth = 1

    with session() as s:
        while active_chains and current_depth < max_hops:
            logger.info(
                f"Peel BFS hop {current_depth}: {len(active_chains)} active chains"
            )

            payload = [
                {
                    "chain_id": chain_id,
                    "current_node": data["current_node"],
                    "current_vol": data["current_vol"],
                }
                for chain_id, data in active_chains.items()
            ]

            all_results = []

            for i in range(0, len(payload), BATCH_SIZE):
                chunk = payload[i : i + BATCH_SIZE]
                chunk_results = s.run(
                    HOP_QUERY,
                    batch=chunk,
                    min_peel=min_peel_amount,
                    max_out_degree=max_out_degree,
                ).data()
                all_results.extend(chunk_results)

            next_active_chains = {}
            chains_with_next_hop = set()
            split_counter = 0

            for row in all_results:
                parent_cid = row["chain_id"]
                chains_with_next_hop.add(parent_cid)
                parent_data = active_chains[parent_cid]

                if len(next_active_chains) >= max_active_chains:
                    continue

                new_cid = f"{parent_cid}_{split_counter}"
                split_counter += 1

                next_active_chains[new_cid] = {
                    "origin_wallet": parent_data["origin_wallet"],
                    "current_node": row["next_node"],
                    "start_vol": parent_data["start_vol"],
                    "current_vol": row["next_vol"],
                    "hashes": parent_data["hashes"] + [row["tx_hash"]],
                    "hop_count": parent_data["hop_count"] + 1,
                }

            for cid, data in active_chains.items():
                if cid not in chains_with_next_hop and data["hop_count"] >= min_hops:
                    completed_chains.append(
                        {
                            "origin_wallet": data["origin_wallet"],
                            "destination_wallet": data["current_node"],
                            "chain_length": data["hop_count"],
                            "starting_volume": data["start_vol"],
                            "ending_volume": data["current_vol"],
                            "associated_tx_hashes": data["hashes"],
                        }
                    )

            active_chains = next_active_chains
            current_depth += 1

        for data in active_chains.values():
            if data["hop_count"] >= min_hops:
                completed_chains.append(
                    {
                        "origin_wallet": data["origin_wallet"],
                        "destination_wallet": data["current_node"],
                        "chain_length": data["hop_count"],
                        "starting_volume": data["start_vol"],
                        "ending_volume": data["current_vol"],
                        "associated_tx_hashes": data["hashes"],
                    }
                )

    if not completed_chains:
        logger.info("No peel chains detected.")
        return []

    _create_alerts(completed_chains)
    logger.info(f"Detected {len(completed_chains)} peel chains and wrote alerts.")

    return completed_chains
