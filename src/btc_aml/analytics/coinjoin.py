from loguru import logger

from ..neo4j_client import session


BATCH_SIZE = 1000


DETECT_QUERY = """
MATCH (t:Tx)
WHERE NOT EXISTS { (t)-[:INPUT]->(:Address {id: 'COINBASE'}) }

MATCH (t)-[i:INPUT]->(a:Address)
MATCH (t)-[o:OUTPUT]->(b:Address)

WITH t,
     count(DISTINCT a) AS input_count,
     count(DISTINCT b) AS output_address_count,
     count(o) AS output_vout_count,
     collect(DISTINCT b) AS receivers,
     collect(o.value_satoshi) AS output_values

WITH t,
     input_count,
     output_address_count,
     output_vout_count,
     receivers,
     output_values,
     (1.0 * abs(input_count - output_address_count)) /
     (CASE WHEN input_count > output_address_count THEN input_count ELSE output_address_count END)
       AS asymmetry_ratio

WHERE input_count >= $min_p
  AND output_address_count >= $min_p
  AND asymmetry_ratio <= $max_asym

UNWIND output_values AS value_satoshi

WITH t,
     input_count,
     output_address_count,
     output_vout_count,
     receivers,
     asymmetry_ratio,
     round(value_satoshi / toFloat($bucket_sats)) AS value_bucket,
     count(*) AS bucket_size

WITH t,
     input_count,
     output_address_count,
     output_vout_count,
     receivers,
     asymmetry_ratio,
     sum(bucket_size) AS total_bucketed_outputs,
     sum(CASE WHEN bucket_size >= 2 THEN bucket_size ELSE 0 END) AS outputs_in_anon_sets

WHERE toFloat(outputs_in_anon_sets) / toFloat(total_bucketed_outputs) >= $anon_ratio

OPTIONAL MATCH (rcv)-[future_spend:SENT]->(future_dest:Address)
WHERE rcv IN receivers

WITH t,
     input_count,
     output_address_count,
     output_vout_count,
     asymmetry_ratio,
     outputs_in_anon_sets,
     count(DISTINCT future_dest) AS unique_future_destinations,
     count(future_spend) AS total_future_spends

WITH t,
     input_count,
     output_address_count,
     output_vout_count,
     asymmetry_ratio,
     outputs_in_anon_sets,
     total_future_spends,
     CASE
       WHEN total_future_spends > 0
       THEN toFloat(unique_future_destinations) / toFloat(total_future_spends)
       ELSE 1.0
     END AS divergence_ratio

WHERE divergence_ratio >= $min_divergence
  AND (NOT $require_future OR total_future_spends > 0)

RETURN t.hash AS tx_hash,
       input_count,
       output_address_count,
       output_vout_count,
       asymmetry_ratio,
       outputs_in_anon_sets,
       divergence_ratio
"""


CREATE_ALERTS_QUERY = """
UNWIND $rows AS row

MERGE (t:Tx {hash: row.tx_hash})

MERGE (al:Alert {alert_id: 'MIXER_' + row.tx_hash})
ON CREATE SET
    al.typology = 'CoinJoin/Mixer',
    al.severity = 'HIGH',
    al.status = 'NEW',
    al.detected_at = timestamp()

SET
    al.tx_hash = row.tx_hash,
    al.input_count = row.input_count,
    al.output_address_count = row.output_address_count,
    al.output_vout_count = row.output_vout_count,
    al.asymmetry_ratio = row.asymmetry_ratio,
    al.outputs_in_anon_sets = row.outputs_in_anon_sets,
    al.divergence_ratio = row.divergence_ratio,
    al.last_detected_at = timestamp()

MERGE (al)-[:ABOUT_TX]->(t)

WITH al

MATCH (t2:Tx {hash: al.tx_hash})-[:INPUT|OUTPUT]->(p:Address)
MERGE (p)-[:FLAGGED_IN]->(al)
"""


def _create_alerts(rows: list[dict]) -> None:
    if not rows:
        return

    with session() as s:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            s.run(CREATE_ALERTS_QUERY, rows=batch)


def detect_and_alert_coinjoins(
    min_participants: int = 50,
    max_asymmetry_ratio: float = 0.20,
    anon_set_ratio: float = 0.35,
    min_divergence_ratio: float = 0.7,
    value_bucket_satoshi: int = 10_000,
    require_future_spends: bool = False,
) -> list[dict]:
    """
    Detect CoinJoin / mixer-like transactions using:
    - actual transaction topology
    - symmetric input/output shape
    - output value clustering / anonymity sets
    - post-transaction divergence
    """
    logger.info("Starting CoinJoin detection...")

    with session() as s:
        rows = s.run(
            DETECT_QUERY,
            min_p=min_participants,
            max_asym=max_asymmetry_ratio,
            anon_ratio=anon_set_ratio,
            min_divergence=min_divergence_ratio,
            bucket_sats=value_bucket_satoshi,
            require_future=require_future_spends,
        ).data()

    if not rows:
        logger.info("No CoinJoin candidates detected.")
        return []

    _create_alerts(rows)
    logger.info(f"Detected {len(rows)} CoinJoin candidates and wrote alerts.")

    return rows
