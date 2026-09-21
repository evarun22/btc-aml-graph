from fastapi import APIRouter, Depends
from api.dependencies import get_neo4j
from api.neo4j_service import Neo4jService

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health(neo4j: Neo4jService = Depends(get_neo4j)):
    try:
        neo4j.scalar("RETURN 1 AS ok")
        neo4j_ok = True
    except Exception:
        neo4j_ok = False

    return {
        "status": "ok",
        "neo4j": neo4j_ok,
    }
