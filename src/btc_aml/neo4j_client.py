from contextlib import contextmanager

from neo4j import Driver, GraphDatabase

from .config import get_settings


_driver: Driver | None = None


def get_driver() -> Driver:
    global _driver

    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        _driver.verify_connectivity()

    return _driver


def close_driver() -> None:
    global _driver

    if _driver is not None:
        _driver.close()
        _driver = None


@contextmanager
def session(database: str | None = None):
    driver = get_driver()
    with driver.session(database=database) as s:
        yield s
