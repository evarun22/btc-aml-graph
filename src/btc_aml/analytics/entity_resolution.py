from loguru import logger

from ..neo4j_client import session


GRAPH_NAME = "cioh_entity_graph"

# --- CO_SPENT materialization controls ------------------------------------
# Transactions with more inputs than this are treated as consolidation
# transactions and excluded: they cause quadratic pair blow-up in memory and
# merge unrelated actors into one component (standard CIOH practice).
CO_SPENT_MAX_INPUTS_PER_TX = 100

# Block heights read per iteration.
CO_SPENT_HEIGHT_BATCH = 1

# Address pairs written per Neo4j transaction.
CO_SPENT_WRITE_BATCH = 5000

# Transactions per iteration when handling txs without block_height.
CO_SPENT_NULL_HEIGHT_BATCH = 200
# -------------------------------------------------------------------------


TEARDOWN_ENTITY_QUERY = """
CALL () {
    MATCH (e:Entity)
    DETACH DELETE e
} IN TRANSACTIONS OF 50000 ROWS
"""


TEARDOWN_CO_SPENT_QUERY = """
CALL () {
    MATCH ()-[c:CO_SPENT]-()
    DELETE c
} IN TRANSACTIONS OF 50000 ROWS
"""


CLEAR_COMPONENT_IDS_QUERY = """
CALL () {
    MATCH (a:Address)
    WHERE a.entity_component_id IS NOT NULL
    REMOVE a.entity_component_id
} IN TRANSACTIONS OF 50000 ROWS
"""


# Reads per-transaction sender lists WITHOUT generating pairs in Cypher.
# Oversized transactions come back with senders = null so the huge lists
# never leave the database.
CO_SPENT_PAIRS_READ_BY_HEIGHT = """
MATCH (t:Tx)-[:INPUT]->(a:Address)
WHERE t.block_height IN $heights
  AND NOT t.hash IN $mixer_hashes

WITH t, collect(DISTINCT a.id) AS senders

RETURN t.hash AS tx_hash,
       size(senders) AS input_count,
       CASE
         WHEN size(senders) > 1 AND size(senders) <= $max_inputs THEN senders
         ELSE null
       END AS senders
"""


CO_SPENT_PAIRS_READ_BY_HASH = """
MATCH (t:Tx)-[:INPUT]->(a:Address)
WHERE t.hash IN $tx_hashes
  AND NOT t.hash IN $mixer_hashes

WITH t, collect(DISTINCT a.id) AS senders

RETURN t.hash AS tx_hash,
       size(senders) AS input_count,
       CASE
         WHEN size(senders) > 1 AND size(senders) <= $max_inputs THEN senders
         ELSE null
       END AS senders
"""


# Directed CO_SPENT, one edge per address pair, weighted by co-spend count.
# GDS projects this relationship as UNDIRECTED, so WCC is unaffected.
CO_SPENT_PAIRS_WRITE = """
UNWIND $rows AS row

MATCH (x:Address {id: row.a})
MATCH (y:Address {id: row.b})

MERGE (x)-[r:CO_SPENT]->(y)
  ON CREATE SET r.co_tx_count = row.co_tx_count,
                r.first_tx_hash = row.tx_hash,
                r.updated_at = timestamp()
  ON MATCH  SET r.co_tx_count = coalesce(r.co_tx_count, 0) + row.co_tx_count,
                r.updated_at = timestamp()
"""


PROJECT_QUERY = f"""
CALL gds.graph.project(
    '{GRAPH_NAME}',
    'Address',
    {{
        CO_SPENT: {{
            orientation: 'UNDIRECTED'
        }}
    }}
)
"""


WCC_QUERY = f"""
CALL gds.wcc.write(
    '{GRAPH_NAME}',
    {{
        writeProperty: 'entity_component_id'
    }}
)
YIELD nodePropertiesWritten, componentCount
RETURN nodePropertiesWritten, componentCount
"""


INSTANTIATE_ENTITIES_QUERY = """
MATCH (a:Address)
WHERE a.entity_component_id IS NOT NULL

CALL (a) {
    MERGE (e:Entity {entity_id: a.entity_component_id})
    MERGE (a)-[:CONTROLLED_BY]->(e)
} IN TRANSACTIONS OF 50000 ROWS
"""


ENTITY_METRICS_QUERY = """
MATCH (e:Entity)<-[:CONTROLLED_BY]-(a:Address)
WITH e,
     count(a) AS address_count,
     sum(coalesce(a.btc_received_actual, 0.0)) AS total_received,
     sum(coalesce(a.btc_spent_actual, 0.0)) AS total_spent
SET e.address_count = address_count,
    e.total_received_btc = total_received,
    e.total_spent_btc = total_spent
"""


def _drop_graph(session) -> None:
    try:
        session.run(
            f"CALL gds.graph.drop('{GRAPH_NAME}') YIELD graphName"
        ).consume()
    except Exception:
        pass


def _accumulate_pairs(
    records: list[dict],
    pair_map: dict[tuple[str, str], list],
) -> int:
    """
    Turn per-transaction sender lists into deduplicated address pairs.

    pair_map[(a, b)] = [first_tx_hash, co_spend_count]
    Returns the number of transactions skipped for being too large.
    """
    skipped = 0

    for record in records:
        senders = record.get("senders")

        if not senders:
            if (record.get("input_count") or 0) > CO_SPENT_MAX_INPUTS_PER_TX:
                skipped += 1
            continue

        ordered = sorted(set(senders))
        tx_hash = record["tx_hash"]

        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                key = (ordered[i], ordered[j])
                existing = pair_map.get(key)

                if existing is None:
                    pair_map[key] = [tx_hash, 1]
                else:
                    existing[1] += 1

    return skipped


def _write_pairs(session, pair_map: dict[tuple[str, str], list]) -> int:
    if not pair_map:
        return 0

    rows = [
        {"a": a, "b": b, "tx_hash": v[0], "co_tx_count": v[1]}
        for (a, b), v in pair_map.items()
    ]

    for i in range(0, len(rows), CO_SPENT_WRITE_BATCH):
        session.run(
            CO_SPENT_PAIRS_WRITE, rows=rows[i : i + CO_SPENT_WRITE_BATCH]
        ).consume()

    return len(rows)


def _materialize_co_spent_edges(session, mixer_hashes: list[str]) -> dict:
    """
    Materialize CO_SPENT edges with bounded memory.

    Pair generation happens in Python, one block height at a time, and writes
    are committed in fixed-size batches. This removes the n^2 UNWIND product
    that previously exhausted dbms.memory.transaction.total.max.
    """
    heights = [
        record["height"]
        for record in session.run(
            """
            MATCH (t:Tx)
            WHERE t.block_height IS NOT NULL
            RETURN DISTINCT t.block_height AS height
            ORDER BY height
            """
        ).data()
    ]

    total_pairs = 0
    skipped_txs = 0

    logger.info(
        f"Materializing CO_SPENT across {len(heights)} block heights "
        f"(max {CO_SPENT_MAX_INPUTS_PER_TX} inputs per tx, "
        f"write batch {CO_SPENT_WRITE_BATCH})."
    )

    for i in range(0, len(heights), CO_SPENT_HEIGHT_BATCH):
        window = heights[i : i + CO_SPENT_HEIGHT_BATCH]

        records = session.run(
            CO_SPENT_PAIRS_READ_BY_HEIGHT,
            heights=window,
            mixer_hashes=mixer_hashes,
            max_inputs=CO_SPENT_MAX_INPUTS_PER_TX,
        ).data()

        pair_map: dict[tuple[str, str], list] = {}
        skipped_txs += _accumulate_pairs(records, pair_map)
        total_pairs += _write_pairs(session, pair_map)

        logger.info(
            f"CO_SPENT heights {window[0]}-{window[-1]} "
            f"({i + len(window)}/{len(heights)}): "
            f"txs={len(records)} pairs={len(pair_map)} cumulative={total_pairs}"
        )

    null_count = session.run(
        """
        MATCH (t:Tx) WHERE t.block_height IS NULL
        RETURN count(t) AS count
        """
    ).single()["count"]

    if null_count:
        logger.info(
            f"Materializing CO_SPENT for {null_count} transactions "
            "without block_height."
        )

        skip = 0

        while True:
            tx_hashes = [
                record["hash"]
                for record in session.run(
                    """
                    MATCH (t:Tx)
                    WHERE t.block_height IS NULL
                    RETURN t.hash AS hash
                    ORDER BY t.hash
                    SKIP $skip LIMIT $limit
                    """,
                    skip=skip,
                    limit=CO_SPENT_NULL_HEIGHT_BATCH,
                ).data()
            ]

            if not tx_hashes:
                break

            records = session.run(
                CO_SPENT_PAIRS_READ_BY_HASH,
                tx_hashes=tx_hashes,
                mixer_hashes=mixer_hashes,
                max_inputs=CO_SPENT_MAX_INPUTS_PER_TX,
            ).data()

            pair_map = {}
            skipped_txs += _accumulate_pairs(records, pair_map)
            total_pairs += _write_pairs(session, pair_map)

            skip += CO_SPENT_NULL_HEIGHT_BATCH

    logger.info(
        f"CO_SPENT materialization finished. unique pair writes={total_pairs}, "
        f"consolidation txs skipped={skipped_txs}"
    )

    return {"pairs_written": total_pairs, "skipped_txs": skipped_txs}


def run_global_entity_resolution(rebuild: bool = True) -> dict:
    """
    Run Common Input Ownership Heuristic entity resolution.

    Steps:
    1. Exclude CoinJoin/mixer transactions
    2. Materialize CO_SPENT edges in bounded batches
    3. Project graph into GDS
    4. Run WCC
    5. Instantiate Entity nodes
    6. Compute entity metrics
    """
    logger.info("Starting global entity resolution...")

    with session() as s:
        if rebuild:
            logger.info("Tearing down old Entity state...")
            s.run(TEARDOWN_ENTITY_QUERY).consume()
            s.run(TEARDOWN_CO_SPENT_QUERY).consume()
            s.run(CLEAR_COMPONENT_IDS_QUERY).consume()

        mixer_hashes = [
            record["tx_hash"]
            for record in s.run(
                """
                MATCH (al:Alert {typology: 'CoinJoin/Mixer'})
                RETURN al.tx_hash AS tx_hash
                """
            ).data()
            if record["tx_hash"]
        ]

        logger.info(f"Excluding {len(mixer_hashes)} mixer transactions from CIOH.")

        co_spent_count = s.run(
            "MATCH ()-[c:CO_SPENT]-() RETURN count(c) AS count"
        ).single()["count"]

        if rebuild or co_spent_count == 0:
            _materialize_co_spent_edges(s, mixer_hashes)

            co_spent_count = s.run(
                "MATCH ()-[c:CO_SPENT]-() RETURN count(c) AS count"
            ).single()["count"]

        logger.info(f"CO_SPENT edge count after materialization: {co_spent_count}")

        if co_spent_count == 0:
            logger.info("No CO_SPENT edges found. Skipping WCC.")
            return {"components": 0, "entities": 0}

        _drop_graph(s)

        logger.info("Projecting CIOH graph into GDS...")
        s.run(PROJECT_QUERY).consume()

        component_count = 0
        nodes_written = 0

        try:
            logger.info("Running WCC...")
            record = s.run(WCC_QUERY).single()

            if record:
                nodes_written = int(record["nodePropertiesWritten"])
                component_count = int(record["componentCount"])
                logger.info(
                    f"WCC complete. "
                    f"Nodes updated: {nodes_written}, "
                    f"components: {component_count}"
                )

            logger.info("Instantiating Entity nodes...")
            s.run(INSTANTIATE_ENTITIES_QUERY).consume()

            logger.info("Computing entity metrics...")
            s.run(ENTITY_METRICS_QUERY).consume()

        finally:
            _drop_graph(s)

        entity_count = s.run(
            "MATCH (e:Entity) RETURN count(e) AS count"
        ).single()["count"]

        logger.info(f"Entity resolution complete. Entities created: {entity_count}")

        return {
            "components": component_count,
            "entities": int(entity_count),
            "nodes_written": nodes_written,
        }
