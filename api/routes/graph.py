from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError
from api.dependencies import get_neo4j
from api.neo4j_service import Neo4jService
from api.services.graph_service import GraphService
from api.schemas.models import Graph
from api.utils.address_validation import validate_address

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph/subgraph", response_model=Graph)
def get_subgraph(
    address: str,
    depth: int = Query(1, ge=1, le=2),
    max_nodes: int = Query(150, ge=10, le=500),
    neo4j: Neo4jService = Depends(get_neo4j),
):
    if not validate_address(address):
        raise HTTPException(status_code=422, detail="Invalid Bitcoin address format")

    try:
        service = GraphService(neo4j)
        return service.address_subgraph(address=address, depth=depth, max_nodes=max_nodes)
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")
