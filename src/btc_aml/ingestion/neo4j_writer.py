from ..config import get_settings
from .utxo_ingest import (
    MERGE_BLOCK,
    MERGE_CHANGE,
    MERGE_INPUT,
    MERGE_OUTPUT,
    MERGE_SENT,
    MERGE_TX,
)


BATCH_SIZE = 2000


def execute_batched(session, query: str, rows: list[dict], **params) -> None:
    if not rows:
        return

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        session.run(query, rows=batch, **params)


def write_tx_graph_rows(session, tx_graph_rows: list[dict], version: str | None = None) -> None:
    settings = get_settings()
    version = version or settings.heuristic_version

    blocks = [row["block"] for row in tx_graph_rows if row.get("block")]
    txs = [row["tx"] for row in tx_graph_rows if row.get("tx")]
    inputs = [item for row in tx_graph_rows for item in row.get("inputs", [])]
    outputs = [item for row in tx_graph_rows for item in row.get("outputs", [])]
    flows = [item for row in tx_graph_rows for item in row.get("flows", [])]
    changes = [item for row in tx_graph_rows for item in row.get("changes", [])]

    execute_batched(session, MERGE_BLOCK, blocks)
    execute_batched(session, MERGE_TX, txs, version=version)
    execute_batched(session, MERGE_INPUT, inputs)
    execute_batched(session, MERGE_OUTPUT, outputs)
    execute_batched(session, MERGE_SENT, flows, version=version)
    execute_batched(session, MERGE_CHANGE, changes, version=version)
