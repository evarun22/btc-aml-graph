import re
from pathlib import Path

import pandas as pd
from loguru import logger

from ..neo4j_client import session


BATCH_SIZE = 5000


BECH32_RE = re.compile(r"^bc1[02-9ac-hj-np-z]+$", re.IGNORECASE)
LEGACY_RE = re.compile(r"^[13][a-km-zA-HJ-NP-Z1-9]+$")


def is_btc_address(value: str) -> bool:
    value = str(value).strip()

    if value.lower().startswith("bc1"):
        return 42 <= len(value) <= 62 and BECH32_RE.match(value) is not None

    if value.startswith(("1", "3")):
        return 26 <= len(value) <= 37 and LEGACY_RE.match(value) is not None

    return False


def _first_valid(row: pd.Series, columns: list[str]) -> str:
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            return str(row[col]).strip()
    return ""


def _extract_candidate_address_columns(df: pd.DataFrame) -> list[str]:
    keywords = ["btc", "bitcoin", "crypto", "address"]
    return [
        col
        for col in df.columns
        if any(keyword in str(col).lower() for keyword in keywords)
    ]


def load_ofac_csv(csv_path: str | Path) -> int:
    """
    Load OFAC sanctioned Bitcoin addresses into Neo4j.

    Expects a CSV export from OFAC where Bitcoin addresses appear
    in one or more columns.
    """
    csv_path = Path(csv_path)

    if not csv_path.exists():
        raise FileNotFoundError(f"OFAC CSV not found: {csv_path}")

    logger.info(f"Loading OFAC CSV from {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)
    address_columns = _extract_candidate_address_columns(df)

    if not address_columns:
        logger.warning("No obvious OFAC address columns found in CSV.")
        return 0

    name_columns = [
        "Name",
        "Full Name",
        "First Name",
        "Last Name",
        "Alias",
        "Also Known As",
    ]
    program_columns = [
        "Sanctions List Program(s)",
        "Program(s)",
        "Program",
        "List",
        "SDN",
    ]
    date_columns = [
        "Date",
        "Listing Date",
        "Designation Date",
        "Date of Designation",
    ]

    rows = []
    seen = set()

    for _, row in df.iterrows():
        name = _first_valid(row, name_columns) or "Unknown"
        program = _first_valid(row, program_columns) or "Unknown"
        listing_date = _first_valid(row, date_columns) or ""

        for col in address_columns:
            raw_value = row.get(col)

            if pd.isna(raw_value):
                continue

            parts = re.split(r"[;,\n]+", str(raw_value))

            for part in parts:
                address = part.strip()

                if not is_btc_address(address):
                    continue

                if address in seen:
                    continue

                seen.add(address)

                rows.append(
                    {
                        "address": address,
                        "name": name,
                        "program": program,
                        "listing_date": listing_date,
                    }
                )

    if not rows:
        logger.warning("No valid Bitcoin addresses extracted from OFAC CSV.")
        return 0

    load_query = """
    UNWIND $rows AS row
    MERGE (a:Address:SanctionedAddress {id: row.address})
    SET a.name = row.name,
        a.program = row.program,
        a.listing_date = row.listing_date,
        a.ofac_distance = 0,
        a.updated_at = timestamp()
    """

    with session() as s:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            s.run(load_query, rows=batch)

    logger.info(f"Loaded {len(rows)} OFAC sanctioned addresses.")
    return len(rows)


def _create_ofac_alert(session, address: str, distance: int) -> None:
    severity = {
        0: "CRITICAL",
        1: "HIGH",
        2: "MEDIUM",
    }.get(distance, "LOW")

    query = """
    MERGE (al:Alert {alert_id: 'OFAC_' + $address + '_' + $distance})
    ON CREATE SET
        al.typology = 'OFAC Exposure',
        al.severity = $severity,
        al.status = 'NEW',
        al.detected_at = timestamp()

    SET
        al.address = $address,
        al.ofac_distance = $distance,
        al.last_detected_at = timestamp()

    MATCH (a:Address {id: $address})
    MERGE (a)-[:FLAGGED_IN]->(al)
    """

    session.run(
        query,
        address=address,
        distance=distance,
        severity=severity,
    )


def check_ofac_proximity(address: str, max_hops: int = 2) -> dict:
    """
    Check exact OFAC match and graph proximity to sanctioned addresses.
    """
    max_hops = int(max_hops)

    with session() as s:
        exact_record = s.run(
            """
            MATCH (a:Address {id: $address})
            WHERE a:SanctionedAddress
            RETURN count(a) AS count
            """,
            address=address,
        ).single()

        distance = 0 if exact_record and exact_record["count"] > 0 else None

        if distance is None:
            path_query = f"""
            MATCH (a:Address {{id: $address}})
            OPTIONAL MATCH p =
                (a)-[:SENT|RETURNED_CHANGE*1..{max_hops}]->(s:Address:SanctionedAddress)
            WITH a, min(length(p)) AS distance
            RETURN distance
            """

            path_record = s.run(path_query, address=address).single()
            distance = path_record["distance"] if path_record else None

        if distance is not None:
            s.run(
                """
                MATCH (a:Address {id: $address})
                SET a.ofac_distance = $distance
                """,
                address=address,
                distance=distance,
            )
            _create_ofac_alert(s, address, distance)
        else:
            s.run(
                """
                MATCH (a:Address {id: $address})
                REMOVE a.ofac_distance
                """,
                address=address
            )


    return {
        "address": address,
        "ofac_distance": distance,
    }

def _has_sanctioned_addresses(session) -> bool:
    record = session.run(
        """
        MATCH (s:Address:SanctionedAddress)
        RETURN count(s) AS count
        """
    ).single()

    return bool(record and record["count"] > 0)

def screen_ofac_for_top_addresses(limit: int = 2000, max_hops: int = 2) -> list[dict]:
    """
    Screen the highest-volume addresses that have not been OFAC-screened yet.
    """
    with session() as s:
        if not _has_sanctioned_addresses(s):
            logger.warning(
                "No SanctionedAddress nodes found. "
                "Skipping OFAC top-address screening. Load OFAC CSV first."
            )
            return []

        addresses = [
            record["id"]
            for record in s.run(
                """
                MATCH (a:Address)
                WHERE a.ofac_distance IS NULL
                RETURN a.id AS id,
                       coalesce(a.btc_received_actual, 0.0) +
                       coalesce(a.btc_spent_actual, 0.0) AS volume
                ORDER BY volume DESC
                LIMIT $limit
                """,
                limit=limit,
            )
        ]

    logger.info(f"Screening top {len(addresses)} addresses for OFAC proximity...")

    results = []
    for address in addresses:
        results.append(check_ofac_proximity(address, max_hops=max_hops))

    flagged_count = sum(1 for r in results if r["ofac_distance"] is not None)
    logger.info(f"OFAC screening complete. Flagged {flagged_count} addresses.")

    return results


def screen_ofac_for_alert_addresses(max_hops: int = 2) -> list[dict]:
    """
    Screen addresses already involved in alerts for OFAC proximity.
    """
    with session() as s:
        if not _has_sanctioned_addresses(s):
            logger.warning(
                "No SanctionedAddress nodes found. "
                "Skipping OFAC alert-address screening. Load OFAC CSV first."
            )
            return []

        addresses = [
            record["id"]
            for record in s.run(
                """
                MATCH (a:Address)-[:FLAGGED_IN]->(:Alert)
                WHERE a.ofac_distance IS NULL
                RETURN DISTINCT a.id AS id
                """
            )
        ]

    logger.info(f"Screening {len(addresses)} alert-related addresses for OFAC proximity...")

    results = []
    for address in addresses:
        results.append(check_ofac_proximity(address, max_hops=max_hops))

    flagged_count = sum(1 for r in results if r["ofac_distance"] is not None)
    logger.info(f"OFAC alert-address screening complete. Flagged {flagged_count} addresses.")

    return results

