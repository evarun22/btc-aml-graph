from pathlib import Path

import pandas as pd
from loguru import logger

from .blockchain.block_fetcher import fetch_block_by_height, fetch_raw_block, fetch_recent_blocks
from .blockchain.tx_fetcher import fetch_address_txs, fetch_tx
from .ingestion.neo4j_writer import write_tx_graph_rows
from .ingestion.proportional_matrix import build_tx_graph_rows
from .maintenance import recompute_address_metrics
from .neo4j_client import session
from .schema import ensure_schema
from .state import ensure_state, get_last_block_height, set_last_block_height


def _ingest_tx_data(
    tx: dict,
    block_hash: str | None = None,
    block_height: int | None = None,
    block_time: int | None = None,
) -> bool:
    rows = build_tx_graph_rows(
        tx=tx,
        block_hash=block_hash,
        block_height=block_height,
        block_time=block_time,
    )

    if not rows:
        return False

    with session() as s:
        write_tx_graph_rows(s, [rows])

    return True


def ingest_block(height: int) -> bool:
    summary = fetch_block_by_height(height)

    if not summary:
        logger.warning(f"No block found for height {height}")
        return False

    raw_block = fetch_raw_block(summary["hash"])
    ingested_count = 0

    for tx in raw_block.get("tx", []):
        if _ingest_tx_data(
            tx=tx,
            block_hash=raw_block.get("hash"),
            block_height=height,
            block_time=raw_block.get("time"),
        ):
            ingested_count += 1

    logger.info(f"Ingested {ingested_count} transactions from block {height}")
    return True


def ingest_blocks(start_height: int, end_height: int) -> None:
    ensure_schema()
    ensure_state()

    for height in range(start_height, end_height + 1):
        ingest_block(height)
        set_last_block_height(height)


def ingest_latest(limit: int = 10) -> list[int]:
    ensure_schema()
    ensure_state()

    summaries = fetch_recent_blocks(limit=limit)
    if not summaries:
        logger.warning("No recent blocks returned")
        return []

    heights = sorted({block["height"] for block in summaries})
    last_height = get_last_block_height()

    ingested_heights = []

    for height in heights:
        if height <= last_height:
            continue

        ingest_block(height)
        set_last_block_height(height)
        ingested_heights.append(height)

    return ingested_heights


def ingest_tx(tx_hash: str) -> bool:
    ensure_schema()
    tx = fetch_tx(tx_hash)
    return _ingest_tx_data(tx=tx)


def ingest_address(address: str, limit: int = 50) -> int:
    ensure_schema()
    txs = fetch_address_txs(address, limit=limit)
    count = 0

    for tx in txs:
        if _ingest_tx_data(tx=tx):
            count += 1

    logger.info(f"Ingested {count} transactions for address {address}")
    return count


def run_all(
    start_height: int | None = None,
    end_height: int | None = None,
    latest_limit: int | None = None,
) -> dict:
    ensure_schema()
    ensure_state()

    if latest_limit:
        ingest_latest(limit=latest_limit)
    elif start_height and end_height:
        ingest_blocks(start_height=start_height, end_height=end_height)
    else:
        logger.info("No ingest range provided. Skipping ingestion.")

    recompute_address_metrics()

    return {
        "last_block_height": get_last_block_height(),
    }


def export_flows_to_csv(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    query = """
    MATCH (a:Address)-[r:SENT|RETURNED_CHANGE]->(b:Address)
    RETURN a.id AS from_address,
           b.id AS to_address,
           r.tx_hash AS tx_hash,
           r.transferred_btc AS transferred_btc,
           r.block_height AS block_height,
           r.time AS time,
           labels(r)[0] AS edge_type
    """

    with session() as s:
        records = [record.data() for record in s.run(query)]

    df = pd.DataFrame(records)
    df.to_csv(path, index=False)

    logger.info(f"Exported {len(df)} flow rows to {path}")
    return path
