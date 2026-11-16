from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "change_me_strong_password"
    neo4j_database: str = "neo4j"

    # Blockchain API
    blockchain_api_base: str = "https://blockchain.info"
    request_timeout_seconds: float = 30.0
    request_sleep_seconds: float = 0.5

    # Pipeline
    heuristic_version: str = "v1-utxo-proportional"
    max_proportional_pairs_per_tx: int = 20_000
    dust_satoshi: int = 546

    # Paths
    data_dir: Path = Path("./data")
    raw_data_dir: Path = Path("./data/raw")
    processed_data_dir: Path = Path("./data/processed")
    ofac_dir: Path = Path("./data/ofac")

    # Logging
    log_level: str = "INFO"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8010

    # AI (optional)
    ai_provider: str = "disabled"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
