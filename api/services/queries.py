ADDRESS_REPORT_QUERY = """
MATCH (a:Address {id: $address})
OPTIONAL MATCH (a)-[:CONTROLLED_BY]->(e:Entity)
WITH a, head(collect(e)) AS e
RETURN a.id AS id,
       a.btc_received_actual AS btc_received_actual,
       a.btc_spent_actual AS btc_spent_actual,
       a.first_seen AS first_seen,
       a.last_seen AS last_seen,
       a.risk_score AS risk_score,
       a.risk_level AS risk_level,
       a.risk_factors AS risk_factors,
       a.ofac_distance AS ofac_distance,
       a.alert_typologies AS alert_typologies,
       labels(a) AS labels,
       e.entity_id AS entity_id,
       e.address_count AS entity_size,
       count { (a)-[:SENT|RETURNED_CHANGE]->() } AS out_degree,
       count { ()-[:SENT|RETURNED_CHANGE]->(a) } AS in_degree
"""

GET_ADDRESS_PROPS_QUERY = """
MATCH (a:Address)
WHERE a.id IN $ids
RETURN a.id AS id,
       a.risk_score AS risk_score,
       a.risk_level AS risk_level,
       a.ofac_distance AS ofac_distance,
       a.btc_received_actual AS btc_received_actual,
       a.btc_spent_actual AS btc_spent_actual,
       labels(a) AS labels
"""

NEIGHBOR_EDGES_QUERY = """
MATCH (x:Address)-[r:SENT|RETURNED_CHANGE]-(y:Address)
WHERE x.id IN $addresses OR y.id IN $addresses
RETURN x.id AS x,
       y.id AS y,
       type(r) AS type,
       r.transferred_btc AS amount,
       r.tx_hash AS tx_hash
LIMIT 5000
"""

CENTER_ENTITY_QUERY = """
MATCH (a:Address {id: $address})-[:CONTROLLED_BY]->(e:Entity)
RETURN e.entity_id AS entity_id,
       e.address_count AS address_count,
       e.risk_score AS risk_score,
       e.risk_level AS risk_level
"""

CENTER_ALERTS_QUERY = """
MATCH (a:Address {id: $address})-[:FLAGGED_IN]->(al:Alert)
RETURN al.alert_id AS alert_id,
       al.typology AS typology,
       al.severity AS severity
"""

TOP_SENDERS_QUERY = """
MATCH (s:Address)-[r:SENT|RETURNED_CHANGE]->(a:Address {id: $address})
RETURN s.id AS counterparty,
       sum(coalesce(r.transferred_btc, 0)) AS btc,
       count(r) AS tx_count
ORDER BY btc DESC
LIMIT 10
"""

TOP_RECEIVERS_QUERY = """
MATCH (a:Address {id: $address})-[r:SENT|RETURNED_CHANGE]->(t:Address)
RETURN t.id AS counterparty,
       sum(coalesce(r.transferred_btc, 0)) AS btc,
       count(r) AS tx_count
ORDER BY btc DESC
LIMIT 10
"""

LIST_ALERTS_QUERY = """
MATCH (al:Alert)
WHERE ($typology IS NULL OR al.typology = $typology)
AND ($severity IS NULL OR al.severity = $severity)
AND ($status IS NULL OR al.status = $status)
AND ($search IS NULL OR toString(al.alert_id) CONTAINS $search OR toString(al.typology) CONTAINS $search)
OPTIONAL MATCH (a:Address)-[:FLAGGED_IN]->(al)
WITH al, count(DISTINCT a) AS participant_count
RETURN al.alert_id AS alert_id,
       al.typology AS typology,
       al.severity AS severity,
       al.status AS status,
       al.detected_at AS detected_at,
       coalesce(al.risk_score, 0) AS risk_score,
       participant_count
ORDER BY al.detected_at DESC
SKIP $offset
LIMIT $limit 
"""

ALERT_DETAIL_QUERY = """
MATCH (al:Alert {alert_id: $alert_id})
OPTIONAL MATCH (a:Address)-[:FLAGGED_IN]->(al)
WITH al, collect(DISTINCT CASE WHEN a IS NULL THEN null ELSE a.id END) AS participants_raw
WITH al, [x IN participants_raw WHERE x IS NOT NULL] AS participants
OPTIONAL MATCH (al)-[:ABOUT_TX]->(t:Tx)
WITH al, participants, collect(DISTINCT CASE WHEN t IS NULL THEN null ELSE t.hash END) AS tx_hashes_raw
WITH al, participants, [x IN tx_hashes_raw WHERE x IS NOT NULL] AS tx_hashes
OPTIONAL MATCH (e:Entity)-[:HAS_RISK_EXPOSURE]->(al)
WITH al, participants, tx_hashes, collect(DISTINCT CASE WHEN e IS NULL THEN null ELSE e.entity_id END) AS entities_raw
WITH al, participants, tx_hashes, [x IN entities_raw WHERE x IS NOT NULL] AS entities
RETURN al AS alert,
       participants,
       tx_hashes,
       entities
"""

LIST_ENTITIES_QUERY = """
MATCH (e:Entity)
OPTIONAL MATCH (e)-[:HAS_RISK_EXPOSURE]->(al:Alert)
WITH e, count(al) AS alert_count
WHERE ($search IS NULL OR toString(e.entity_id) CONTAINS $search)
RETURN toString(e.entity_id) AS entity_id,
       e.address_count AS address_count,
       e.total_received_btc AS total_received_btc,
       e.total_spent_btc AS total_spent_btc,
       e.risk_score AS risk_score,
       e.risk_level AS risk_level,
       alert_count
ORDER BY coalesce(e.risk_score, 0) DESC
SKIP $offset
LIMIT $limit 
"""

ENTITY_DETAIL_QUERY = """
MATCH (e:Entity {entity_id: $entity_id})
OPTIONAL MATCH (a:Address)-[:CONTROLLED_BY]->(e)
WITH e, collect(a) AS address_nodes
WITH e, [x IN address_nodes WHERE x IS NOT NULL | {
    id: x.id,
    risk_score: x.risk_score,
    risk_level: x.risk_level,
    btc_received_actual: x.btc_received_actual,
    btc_spent_actual: x.btc_spent_actual
}] AS addresses
OPTIONAL MATCH (e)-[:HAS_RISK_EXPOSURE]->(al:Alert)
WITH e, addresses, collect(DISTINCT CASE WHEN al IS NULL THEN null ELSE al.alert_id END) AS alerts_raw
WITH e, addresses, [x IN alerts_raw WHERE x IS NOT NULL] AS alerts
RETURN e AS entity,
       addresses,
       alerts
"""

OFAC_EXACT_QUERY = """
MATCH (s:Address:SanctionedAddress {id: $address})
RETURN s.id AS id,
       s.name AS name,
       s.program AS program,
       s.listing_date AS listing_date
"""

OFAC_EXISTING_QUERY = """
MATCH (a:Address {id: $address})
RETURN a.ofac_distance AS ofac_distance,
       labels(a) AS labels
"""

OFAC_PROXIMITY_QUERY = """
MATCH (a:Address {id: $address})
OPTIONAL MATCH p = (a)-[:SENT|RETURNED_CHANGE*1..2]->(s:Address:SanctionedAddress)
WITH a, min(length(p)) AS distance
RETURN distance
"""

OFAC_EXPOSURE_QUERY = """
MATCH (a:Address {id: $address})-[r:SENT|RETURNED_CHANGE]->(s:Address:SanctionedAddress)
RETURN s.id AS sanctioned_address,
       s.name AS name,
       s.program AS program,
       count(r) AS tx_count,
       sum(coalesce(r.transferred_btc, 0)) AS exposure_btc
"""

OFAC_TOP_EXPOSURE_QUERY = """
MATCH (a:Address)
WHERE a.ofac_distance IS NOT NULL AND NOT a:SanctionedAddress
RETURN a.id AS address,
       a.ofac_distance AS ofac_distance,
       a.risk_score AS risk_score,
       a.btc_received_actual AS btc_received_actual
ORDER BY a.ofac_distance ASC, coalesce(a.risk_score, 0) DESC
LIMIT $limit
"""
