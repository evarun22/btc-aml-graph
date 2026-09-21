from typing import Any
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError


class Neo4jService:
    def __init__(self, uri: str, user: str, password: str, database: str):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def connect(self) -> None:
        self.driver.verify_connectivity()

    def close(self) -> None:
        self.driver.close()

    def query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.driver.session(database=self.database) as session:
            result = session.run(query, **(params or {}))
            rows = [dict(record) for record in result]
            return rows[:limit] if limit else rows

    def query_one(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        rows = self.query(query, params=params, limit=1)
        return rows[0] if rows else None

    def scalar(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> Any | None:
        row = self.query_one(query, params=params)
        if not row:
            return None
        return next(iter(row.values()))

    def gds_available(self) -> bool:
        try:
            self.scalar("CALL gds.list() YIELD name RETURN count(name) AS c")
            return True
        except Neo4jError:
            return False
