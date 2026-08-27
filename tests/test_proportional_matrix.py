from btc_aml.ingestion.proportional_matrix import build_tx_graph_rows


def test_build_tx_graph_rows_basic():
    tx = {
        "hash": "tx1",
        "fee": 1000,
        "time": 123,
        "block_height": 1,
        "inputs": [
            {"prev_out": {"addr": "A", "value": 1000}},
            {"prev_out": {"addr": "B", "value": 3000}},
        ],
        "out": [
            {"addr": "X", "value": 1500},
            {"addr": "Y", "value": 2000},
            {"addr": "Z", "value": 500},
        ],
    }

    rows = build_tx_graph_rows(
        tx=tx,
        block_hash="block1",
        block_height=1,
        block_time=123,
    )

    assert rows is not None
    assert len(rows["inputs"]) == 2
    assert len(rows["outputs"]) == 3
    assert len(rows["flows"]) > 0


def test_flow_totals_match_outputs():
    tx = {
        "hash": "tx2",
        "fee": 0,
        "time": 123,
        "block_height": 1,
        "inputs": [
            {"prev_out": {"addr": "A", "value": 1000}},
            {"prev_out": {"addr": "B", "value": 3000}},
        ],
        "out": [
            {"addr": "X", "value": 1500},
            {"addr": "Y", "value": 2000},
            {"addr": "Z", "value": 500},
        ],
    }

    rows = build_tx_graph_rows(
        tx=tx,
        block_hash="block1",
        block_height=1,
        block_time=123,
    )

    totals = {}
    for flow in rows["flows"] + rows["changes"]:
        totals[flow["to_address"]] = (
            totals.get(flow["to_address"], 0) + flow["edge_satoshi"]
        )

    assert totals["X"] == 1500
    assert totals["Y"] == 2000
    assert totals["Z"] == 500
