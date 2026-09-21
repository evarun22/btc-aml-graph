from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError
from api.dependencies import get_neo4j
from api.neo4j_service import Neo4jService
from api.services.entity_service import EntityService
from api.schemas.models import EntityDetail, EntitySummary, Graph

router = APIRouter(prefix="/api", tags=["entities"])


@router.get("/entities", response_model=list[EntitySummary])
def list_entities(
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = EntityService(neo4j)
        return service.list_entities(search=search, limit=limit, offset=offset)
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")


@router.get("/entities/{entity_id}", response_model=EntityDetail)
def get_entity(
    entity_id: str,
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = EntityService(neo4j)
        return service.get_entity(entity_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Entity not found")
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")


@router.get("/entities/{entity_id}/graph", response_model=Graph)
def get_entity_graph(
    entity_id: str,
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = EntityService(neo4j)
        return service.get_entity(entity_id).graph
    except KeyError:
        raise HTTPException(status_code=404, detail="Entity not found")
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")
