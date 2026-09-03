from loguru import logger

from ..neo4j_client import session


GRAPH_NAME = "cioh_entity_graph"


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



MATERIALIZE_CO_SPENT_QUERY = """
MATCH (t:Tx)
WHERE NOT t.hash IN $mixer_hashes

MATCH (t)-[:INPUT]->(a:Address)

WITH t, collect(DISTINCT a) AS senders
WHERE size(senders) > 1

UNWIND senders AS s1
UNWIND senders AS s2

WITH t, s1, s2
WHERE elementId(s1) < elementId(s2)

MERGE (s1)-[:CO_SPENT {tx_hash: t.hash}]-(s2)
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
        session.run(f"CALL gds.graph.drop('{GRAPH_NAME}') YIELD graphName")
    except Exception:
        pass


def run_global_entity_resolution(rebuild: bool = True) -> dict:
    """
    Run Common Input Ownership Heuristic entity resolution.

    Steps:
    1. Exclude CoinJoin/mixer transactions
    2. Materialize CO_SPENT edges
    3. Project graph into GDS
    4. Run WCC
    5. Instantiate Entity nodes
    6. Compute entity metrics
    """
    logger.info("Starting global entity resolution...")

    with session() as s:
        if rebuild:
            logger.info("Tearing down old Entity state...")
            s.run(TEARDOWN_ENTITY_QUERY)
            s.run(TEARDOWN_CO_SPENT_QUERY)
            s.run(CLEAR_COMPONENT_IDS_QUERY)

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

        co_spent_count = (
            s.run("MATCH ()-[c:CO_SPENT]-() RETURN count(c) AS count").single()["count"]
        )

        if rebuild or co_spent_count == 0:
            logger.info("Materializing CO_SPENT edges...")
            s.run(MATERIALIZE_CO_SPENT_QUERY, mixer_hashes=mixer_hashes)

            co_spent_count = (
                s.run("MATCH ()-[c:CO_SPENT]-() RETURN count(c) AS count").single()["count"]
            )

        if co_spent_count == 0:
            logger.info("No CO_SPENT edges found. Skipping WCC.")
            return {"components": 0, "entities": 0}

        logger.info("Projecting CIOH graph into GDS...")
        s.run(PROJECT_QUERY)

        component_count = 0
        nodes_written = 0

        try:
            logger.info("Running WCC...")
            record = s.run(WCC_QUERY).single()

            if record:
                nodes_written = int(record["nodePropertiesWritten"])
                component_count = int(record["componentCount"])
                logger.info(
                    f"WCC complete. Nodes updated: {nodes_written}, components: {component_count}"
                )

            logger.info("Instantiating Entity nodes...")
            s.run(INSTANTIATE_ENTITIES_QUERY)

            logger.info("Computing entity metrics...")
            s.run(ENTITY_METRICS_QUERY)

        finally:
            _drop_graph(s)

        entity_count = s.run("MATCH (e:Entity) RETURN count(e) AS count").single()["count"]

        logger.info(f"Entity resolution complete. Entities created: {entity_count}")

        return {
            "components": component_count,
            "entities": int(entity_count),
            "nodes_written": nodes_written,
        }
