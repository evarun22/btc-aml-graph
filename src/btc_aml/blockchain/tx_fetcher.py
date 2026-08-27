import json

from ..config import get_settings
from .client import BlockchainClient
from .block_fetcher import _cache_path


def fetch_tx(tx_hash: str, use_cache: bool = True):
    client = BlockchainClient()
    path = f"/rawtx/{tx_hash}"
    cache_file = _cache_path("rawtx", tx_hash) if use_cache else None

    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text())

    data = client.get_json(path)

    if cache_file:
        cache_file.write_text(json.dumps(data, indent=2))

    return data


def fetch_address_txs(address: str, limit: int = 50, use_cache: bool = True):
    client = BlockchainClient()
    path = f"/rawaddr/{address}?limit={limit}"
    cache_file = _cache_path("address", f"{address}_{limit}") if use_cache else None

    data = _load_or_fetch(client, path, cache_file)

    if isinstance(data, dict):
        return data.get("txs", [])

    return []
