from ..config import get_settings


def _to_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_outputs(tx: dict):
    outputs = []
    for out in tx.get("out", []):
        addr = out.get("addr")
        value = _to_int(out.get("value"))
        if addr and value >= 0:
            outputs.append(
                {
                    "address": addr,
                    "value_satoshi": value,
                }
            )
    return outputs


def _extract_inputs(tx: dict, total_output_value: int):
    inputs = []
    coinbase_added = False

    for inp in tx.get("inputs", []):
        prev_out = inp.get("prev_out") or {}
        addr = prev_out.get("addr")
        value = _to_int(prev_out.get("value"))

        if addr:
            inputs.append(
                {
                    "address": addr,
                    "value_satoshi": value,
                    "is_coinbase": False,
                }
            )
        else:
            if not coinbase_added:
                inputs.append(
                    {
                        "address": "COINBASE",
                        "value_satoshi": total_output_value,
                        "is_coinbase": True,
                    }
                )
                coinbase_added = True

    return inputs


def _aggregate_flows(flows: list[dict], dust_satoshi: int):
    aggregated = {}

    for flow in flows:
        key = (
            flow["from_address"],
            flow["to_address"],
            flow["tx_hash"],
            flow["edge_type"],
        )

        if key not in aggregated:
            aggregated[key] = {
                "from_address": flow["from_address"],
                "to_address": flow["to_address"],
                "tx_hash": flow["tx_hash"],
                "edge_type": flow["edge_type"],
                "is_explicit_change": flow["is_explicit_change"],
                "block_height": flow["block_height"],
                "time": flow["time"],
                "edge_satoshi_sum": flow["edge_satoshi"],
                "edge_fee_satoshi_sum": flow["edge_fee_satoshi"],
            }
        else:
            aggregated[key]["edge_satoshi_sum"] += flow["edge_satoshi"]
            aggregated[key]["edge_fee_satoshi_sum"] += flow["edge_fee_satoshi"]

    sent_flows = []
    change_flows = []

    for row in aggregated.values():
        edge_satoshi = row.pop("edge_satoshi_sum")
        edge_fee_satoshi = row.pop("edge_fee_satoshi_sum")

        row["edge_satoshi"] = edge_satoshi
        row["transferred_btc"] = round(edge_satoshi / 100_000_000, 8)
        row["edge_fee_satoshi"] = edge_fee_satoshi
        row["is_dust"] = edge_satoshi < dust_satoshi

        if row["edge_type"] == "SENT":
            sent_flows.append(row)
        else:
            change_flows.append(row)

    return sent_flows, change_flows


def build_tx_graph_rows(
    tx: dict,
    block_hash: str | None = None,
    block_height: int | None = None,
    block_time: int | None = None,
    max_pairs: int | None = None,
    dust_satoshi: int | None = None,
):
    settings = get_settings()

    tx_hash = tx.get("hash")
    if not tx_hash:
        return None

    fee_satoshi = _to_int(tx.get("fee"))
    timestamp = _to_int(tx.get("time") or block_time)
    height = _to_int(block_height or tx.get("block_height"), default=-1)
    block_hash = block_hash or tx.get("block_hash")

    max_pairs = max_pairs or settings.max_proportional_pairs_per_tx
    dust_satoshi = dust_satoshi or settings.dust_satoshi

    outputs = _extract_outputs(tx)
    total_output_value = sum(o["value_satoshi"] for o in outputs)
    inputs = _extract_inputs(tx, total_output_value)

    total_input_value = sum(i["value_satoshi"] for i in inputs)

    if not inputs or not outputs or total_input_value <= 0:
        return None

    tx_row = {
        "hash": tx_hash,
        "block_hash": block_hash,
        "block_height": height,
        "time": timestamp,
        "fee_satoshi": fee_satoshi,
        "proportional_skipped": False,
    }

    input_rows = [
        {
            "tx_hash": tx_hash,
            "address": i["address"],
            "value_satoshi": i["value_satoshi"],
        }
        for i in inputs
    ]

    output_rows = [
        {
            "tx_hash": tx_hash,
            "address": o["address"],
            "value_satoshi": o["value_satoshi"],
        }
        for o in outputs
    ]

    raw_flows = []

    if len(inputs) * len(outputs) > max_pairs:
        tx_row["proportional_skipped"] = True
    else:
        n_outputs = len(outputs)

        for inp in inputs:
            input_weight_ratio = inp["value_satoshi"] / total_input_value

            for out in outputs:
                edge_satoshi = round(out["value_satoshi"] * input_weight_ratio)
                is_change = inp["address"] == out["address"]
                edge_type = "RETURNED_CHANGE" if is_change else "SENT"

                raw_flows.append(
                    {
                        "from_address": inp["address"],
                        "to_address": out["address"],
                        "tx_hash": tx_hash,
                        "edge_type": edge_type,
                        "is_explicit_change": is_change,
                        "block_height": height,
                        "time": timestamp,
                        "edge_satoshi": edge_satoshi,
                        "edge_fee_satoshi": (
                            round(fee_satoshi * input_weight_ratio / n_outputs)
                            if n_outputs
                            else 0
                        ),
                    }
                )

    sent_flows, change_flows = _aggregate_flows(raw_flows, dust_satoshi)

    block_row = (
        {
            "hash": block_hash,
            "height": height,
            "time": timestamp,
        }
        if block_hash
        else None
    )

    return {
        "block": block_row,
        "tx": tx_row,
        "inputs": input_rows,
        "outputs": output_rows,
        "flows": sent_flows,
        "changes": change_flows,
    }
