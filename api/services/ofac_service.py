from typing import Any
from api.neo4j_service import Neo4jService
from api.schemas.models import OfacCheck
from api.services.queries import (
    OFAC_EXACT_QUERY,
    OFAC_EXISTING_QUERY,
    OFAC_PROXIMITY_QUERY,
    OFAC_EXPOSURE_QUERY,
    OFAC_TOP_EXPOSURE_QUERY,
)
from api.utils.address_validation import validate_address


class OfacService:
    def __init__(self, neo4j: Neo4jService):
        self.neo4j = neo4j

    def check(self, address: str) -> OfacCheck:
        if not validate_address(address):
            raise ValueError("Invalid Bitcoin address format")

        exact_rows = self.neo4j.query(OFAC_EXACT_QUERY, {"address": address})
        if exact_rows:
            programs = sorted({row.get("program") for row in exact_rows if row.get("program")})
            names = sorted({row.get("name") for row in exact_rows if row.get("name")})
            listing_dates = [row.get("listing_date") for row in exact_rows if row.get("listing_date")]

            return OfacCheck(
                address=address,
                exists=True,
                exact_match=True,
                distance=0,
                programs=programs,
                names=names,
                listing_dates=listing_dates,
                exposure_btc=0.0,
                tx_count=0,
                details=exact_rows,
            )

        existing = self.neo4j.query_one(OFAC_EXISTING_QUERY, {"address": address})
        if not existing:
            return OfacCheck(
                address=address,
                exists=False,
                exact_match=False,
                distance=None,
            )

        distance = existing.get("ofac_distance")
        if distance is None:
            prox = self.neo4j.query_one(OFAC_PROXIMITY_QUERY, {"address": address})
            if prox and prox.get("distance") is not None:
                distance = prox["distance"]

        exposure_rows = self.neo4j.query(OFAC_EXPOSURE_QUERY, {"address": address})
        total_exposure = sum(float(row.get("exposure_btc") or 0.0) for row in exposure_rows)
        total_tx_count = sum(int(row.get("tx_count") or 0) for row in exposure_rows)
        programs = sorted({row.get("program") for row in exposure_rows if row.get("program")})
        names = sorted({row.get("name") for row in exposure_rows if row.get("name")})

        return OfacCheck(
            address=address,
            exists=True,
            exact_match=False,
            distance=distance,
            programs=programs,
            names=names,
            listing_dates=[],
            exposure_btc=round(total_exposure, 8),
            tx_count=total_tx_count,
            details=exposure_rows,
        )

    def top_exposure(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.neo4j.query(OFAC_TOP_EXPOSURE_QUERY, {"limit": limit})
