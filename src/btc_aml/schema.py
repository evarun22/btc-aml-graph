from .neo4j_client import session


CONSTRAINTS = [
    """
    CREATE CONSTRAINT address_id_unique IF NOT EXISTS
    FOR (a:Address)
    REQUIRE a.id IS UNIQUE
    """,
    """
    CREATE CONSTRAINT block_hash_unique IF NOT EXISTS
    FOR (b:Block)
    REQUIRE b.hash IS UNIQUE
    """,
    """
    CREATE CONSTRAINT tx_hash_unique IF NOT EXISTS
    FOR (t:Tx)
    REQUIRE t.hash IS UNIQUE
    """,
    """
    CREATE CONSTRAINT alert_id_unique IF NOT EXISTS
    FOR (al:Alert)
    REQUIRE al.alert_id IS UNIQUE
    """,
]


INDEXES = [
    """
    CREATE INDEX address_id_index IF NOT EXISTS
    FOR (a:Address)
    ON (a.id)
    """,
    """
    CREATE INDEX tx_hash_index IF NOT EXISTS
    FOR (t:Tx)
    ON (t.hash)
    """,
    """
    CREATE INDEX block_height_index IF NOT EXISTS
    FOR (b:Block)
    ON (b.height)
    """,
    """
    CREATE INDEX alert_typology_index IF NOT EXISTS
    FOR (al:Alert)
    ON (al.typology)
    """,
]


def ensure_schema() -> None:
    with session() as s:
        for query in CONSTRAINTS:
            s.run(query)
        for query in INDEXES:
            s.run(query)
