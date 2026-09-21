from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError
from api.dependencies import get_neo4j
from api.neo4j_service import Neo4jService
from api.services.ofac_service import OfacService
from api.schemas.models import OfacCheck

router = APIRouter(prefix="/api", tags=["ofac"])


@router.get("/ofac/check", response_model=OfacCheck)
def ofac_check(
    address: str,
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = OfacService(neo4j)
        return service.check(address)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")


@router.get("/ofac/exposure")
def ofac_exposure(
    limit: int = Query(50, ge=1, le=200),
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = OfacService(neo4j)
        return service.top_exposure(limit=limit)
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")
