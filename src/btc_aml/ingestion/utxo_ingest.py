MERGE_BLOCK = """
UNWIND $rows AS row
MERGE (b:Block {hash: row.hash})
SET b.height = row.height,
    b.time = row.time
"""


MERGE_TX = """
UNWIND $rows AS row
MERGE (t:Tx {hash: row.hash})
SET t.block_height = row.block_height,
    t.time = row.time,
    t.fee_satoshi = row.fee_satoshi,
    t.heuristic_version = $version
WITH t, row
OPTIONAL MATCH (b:Block {hash: row.block_hash})
WITH t, b
WHERE b IS NOT NULL
MERGE (b)-[:CONTAINS]->(t)
"""


MERGE_INPUT = """
UNWIND $rows AS row
MERGE (a:Address {id: row.address})
MERGE (t:Tx {hash: row.tx_hash})
MERGE (t)-[r:INPUT]->(a)
SET r.value_satoshi = row.value_satoshi
"""


MERGE_OUTPUT = """
UNWIND $rows AS row
MERGE (a:Address {id: row.address})
MERGE (t:Tx {hash: row.tx_hash})
MERGE (t)-[r:OUTPUT]->(a)
SET r.value_satoshi = row.value_satoshi
"""


MERGE_SENT = """
UNWIND $rows AS row
MERGE (s:Address {id: row.from_address})
MERGE (r:Address {id: row.to_address})
MERGE (s)-[rel:SENT {tx_hash: row.tx_hash}]->(r)
SET rel.transferred_btc = row.transferred_btc,
    rel.block_height = row.block_height,
    rel.time = row.time,
    rel.heuristic_version = $version
"""


MERGE_CHANGE = """
UNWIND $rows AS row
MERGE (s:Address {id: row.from_address})
MERGE (c:Address {id: row.to_address})
MERGE (s)-[rel:RETURNED_CHANGE {tx_hash: row.tx_hash}]->(c)
SET rel.transferred_btc = row.transferred_btc,
    rel.block_height = row.block_height,
    rel.time = row.time,
    rel.is_dust = row.is_dust,
    rel.heuristic_version = $version
"""
