import json
import time
from pathlib import Path

from ..config import get_settings
from .client import BlockchainClient


def _cache_path(kind: str, key: str) -> Path:
    settings = get_settings()
    directory = settings.raw_data_dir / kind
    directory.mkdir(parents=True, exist_ok=True)
    safe_key = str(key).replace("/", "_")
    return directory / f"{safe_key}.json"


def _load_or_fetch(client: BlockchainClient, path: str, cache_file: Path | None = None):
    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text())

    data = client.get_json(path)

    if cache_file:
        cache_file.write_text(json.dumps(data, indent=2))

    return data


def fetch_recent_blocks(limit: int = 10):
    client = BlockchainClient()
    path = f"/blocks/{int(time.time() * 1000)}?format=json"
    data = client.get_json(path)

    if isinstance(data, dict):
        data = data.get("blocks", [])

    return data[:limit]


def fetch_block_by_height(height: int, use_cache: bool = True):
    client = BlockchainClient()
    path = f"/block-height/{height}?format=json"
    cache_file = _cache_path("block_height", height) if use_cache else None

    data = _load_or_fetch(client, path, cache_file)

    if isinstance(data, dict):
        blocks = data.get("blocks", [])
    else:
        blocks = []

    return blocks[0] if blocks else None


def fetch_raw_block(block_hash: str, use_cache: bool = True):
    client = BlockchainClient()
    path = f"/rawblock/{block_hash}"
    cache_file = _cache_path("rawblock", block_hash) if use_cache else None

    return _load_or_fetch(client, path, cache_file)
