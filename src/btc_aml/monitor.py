import os
import time
from contextlib import contextmanager
from pathlib import Path

import fcntl
from loguru import logger

from .pipeline import ingest_latest, run_analytics
from .state import get_last_block_height


STATE_DIR = Path(".state")
LOCK_FILE = STATE_DIR / "monitor.lock"


@contextmanager
def monitor_lock(lock_path: Path = LOCK_FILE):
    """
    Simple file lock to prevent duplicate local monitor processes.

    This is intentionally lightweight.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    f = lock_path.open("a+")

    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        f.close()
        raise RuntimeError(
            "Another monitor process is already running. "
            "Stop it first or remove the stale lock file."
        ) from exc

    f.seek(0)
    f.truncate()
    f.write(str(os.getpid()))
    f.flush()

    try:
        yield
    finally:
        fcntl.flock(f, fcntl.LOCK_UN)
        f.close()


def run_monitor(
    interval_seconds: int = 600,
    limit: int = 10,
    analytics_every: int = 100,
    max_iterations: int = 0,
) -> None:
    """
    Run the continuous ingestion monitor.

    Behavior:
    - repeatedly ingests new blocks
    - tracks how many new blocks have been ingested
    - optionally reruns analytics every N new blocks
    - uses a lock file to avoid duplicate monitors
    """
    with monitor_lock():
        logger.info(
            "Starting monitor: "
            f"interval={interval_seconds}s, "
            f"limit={limit}, "
            f"analytics_every={analytics_every}, "
            f"max_iterations={max_iterations}"
        )

        blocks_since_analytics = 0
        iterations = 0

        while True:
            try:
                last_before = get_last_block_height()
                logger.info(f"Monitor iteration. Current height: {last_before}")

                ingested_heights = ingest_latest(limit=limit)

                if ingested_heights:
                    blocks_since_analytics += len(ingested_heights)
                    logger.info(
                        f"Ingested {len(ingested_heights)} new blocks: "
                        f"{ingested_heights}"
                    )
                else:
                    logger.info("No new blocks to ingest.")

                if analytics_every > 0 and blocks_since_analytics >= analytics_every:
                    logger.info(
                        "Running periodic analytics after "
                        f"{blocks_since_analytics} new blocks..."
                    )
                    run_analytics()
                    blocks_since_analytics = 0

            except Exception:
                logger.exception("Monitor iteration failed. Retrying after interval.")

            iterations += 1

            if max_iterations > 0 and iterations >= max_iterations:
                logger.info("Max iterations reached. Exiting monitor.")
                break

            time.sleep(interval_seconds)
