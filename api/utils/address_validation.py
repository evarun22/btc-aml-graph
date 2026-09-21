import re
from typing import Optional


def validate_address(address: str) -> Optional[str]:
    if not address:
        return None

    addr = address.strip()

    if re.fullmatch(r"bc1[a-z0-9]{8,90}", addr.lower()):
        return "bech32"

    if re.fullmatch(r"1[a-km-zA-HJ-NP-Z1-9]{25,34}", addr):
        return "p2pkh"

    if re.fullmatch(r"3[a-km-zA-HJ-NP-Z1-9]{25,34}", addr):
        return "p2sh"

    return None


def derive_flags(
    labels: list[str] | None,
    ofac_distance: int | None,
    alert_typologies: list[str] | None,
    risk_level: str | None,
    out_degree: int = 0,
    in_degree: int = 0,
) -> list[str]:
    flags: list[str] = []
    labels = labels or []

    if "SanctionedAddress" in labels:
        flags.append("OFAC_EXACT")
    elif ofac_distance == 1:
        flags.append("OFAC_1HOP")
    elif ofac_distance == 2:
        flags.append("OFAC_2HOP")

    for typology in alert_typologies or []:
        if typology:
            flags.append(str(typology).upper().replace(" ", "_"))

    if risk_level:
        flags.append(f"RISK_{risk_level}")

    if out_degree >= 50:
        flags.append("HIGH_OUT_DEGREE")

    if in_degree >= 50:
        flags.append("HIGH_IN_DEGREE")

    return flags
