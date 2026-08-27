import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..config import get_settings


class BlockchainClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        sleep_seconds: float | None = None,
    ):
        settings = get_settings()

        self.base_url = (base_url or settings.blockchain_api_base).rstrip("/")
        self.timeout = timeout or settings.request_timeout_seconds
        self.sleep_seconds = (
            sleep_seconds
            if sleep_seconds is not None
            else settings.request_sleep_seconds
        )

        self.session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_json(self, path: str, params: dict | None = None):
        url = f"{self.base_url}{path}"
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)

        return data
