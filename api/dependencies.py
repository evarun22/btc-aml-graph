from fastapi import Request
from api.neo4j_service import Neo4jService


def get_neo4j(request: Request) -> Neo4jService:
    return request.app.state.neo4j
