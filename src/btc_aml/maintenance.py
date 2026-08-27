from loguru import logger

from .neo4j_client import session


def recompute_address_metrics() -> None:
    with session() as s:
        s.run(
            """
            MATCH (a:Address)
            OPTIONAL MATCH (t)-[o:OUTPUT]->(a)
            WITH a, sum(coalesce(o.value_satoshi, 0)) AS received_sats
            SET a.btc_received_actual = round(received_sats / 100000000.0, 8)
            """
        )

        s.run(
            """
            MATCH (a:Address)
            OPTIONAL MATCH (t)-[i:INPUT]->(a)
            WITH a, sum(coalesce(i.value_satoshi, 0)) AS spent_sats
            SET a.btc_spent_actual = round(spent_sats / 100000000.0, 8)
            """
        )

        s.run(
            """
            MATCH (a:Address)
            OPTIONAL MATCH (t)-[:INPUT|OUTPUT]->(a)
            WITH a,
                 min(t.time) AS first_seen,
                 max(t.time) AS last_seen
            SET a.first_seen = first_seen,
                a.last_seen = last_seen
            """
        )

    logger.info("Address metrics recomputed.")


def get_data_quality_summary() -> dict:
    summary = {}

    with session() as s:
        for label in ["Block", "Tx", "Address", "Alert"]:
            record = s.run(
                f"MATCH (n:{label}) RETURN count(n) AS count"
            ).single()
            summary[label] = int(record["count"]) if record else 0

        unknown_record = s.run(
            """
            MATCH (a:Address)
            WHERE a.id STARTS WITH 'UNKNOWN_INPUT'
            RETURN count(a) AS count
            """
        ).single()
        summary["UnknownInputAddresses"] = (
            int(unknown_record["count"]) if unknown_record else 0
        )

    return summary


def reset_database(confirm: bool = False) -> None:
    if not confirm:
        raise ValueError("Refusing to reset database. Pass confirm=True.")

    logger.warning("Resetting database. This will delete all data.")

    with session() as s:
        s.run(
            """
            CALL {
                MATCH (n)
                DETACH DELETE n
            } IN TRANSACTIONS OF 50000 ROWS
            """
        )

        try:
            s.run("CALL apoc.schema.assert({}, {})")
            logger.info("Dropped constraints and indexes via APOC.")
        except Exception as exc:
            logger.warning(f"Could not drop schema via APOC: {exc}")
