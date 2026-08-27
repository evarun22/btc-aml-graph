from .neo4j_client import session


STATE_NAME = "btc_main"


def ensure_state() -> None:
    with session() as s:
        s.run(
            """
            MERGE (s:PipelineState {name: $name})
            SET s.last_block_height = coalesce(s.last_block_height, -1),
                s.updated_at = timestamp()
            """,
            name=STATE_NAME,
        )


def get_last_block_height() -> int:
    ensure_state()

    with session() as s:
        record = s.run(
            """
            MATCH (s:PipelineState {name: $name})
            RETURN s.last_block_height AS last_block_height
            """,
            name=STATE_NAME,
        ).single()

    return int(record["last_block_height"]) if record else -1


def set_last_block_height(height: int) -> None:
    with session() as s:
        s.run(
            """
            MERGE (s:PipelineState {name: $name})
            SET s.last_block_height = $height,
                s.updated_at = timestamp()
            """,
            name=STATE_NAME,
            height=height,
        )


def get_pipeline_status() -> dict:
    ensure_state()

    with session() as s:
        record = s.run(
            """
            MATCH (s:PipelineState {name: $name})
            RETURN s.last_block_height AS last_block_height,
                   s.updated_at AS updated_at
            """,
            name=STATE_NAME,
        ).single()

    return {
        "last_block_height": int(record["last_block_height"]) if record else -1,
        "updated_at": record["updated_at"] if record else None,
    }
