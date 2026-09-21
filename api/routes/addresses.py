from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError
from api.dependencies import get_neo4j
from api.neo4j_service import Neo4jService
from api.services.address_service import AddressService
from api.services.graph_service import GraphService
from api.schemas.models import AddressReport, Graph

router = APIRouter(prefix="/api/addresses", tags=["addresses"])


@router.get("/{address}", response_model=AddressReport)
def get_address(
    address: str,
    depth: int = Query(1, ge=1, le=2),
    max_nodes: int = Query(120, ge=10, le=500),
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = AddressService(neo4j)
        return service.get_report(address=address, depth=depth, max_nodes=max_nodes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")


@router.get("/{address}/graph", response_model=Graph)
def get_address_graph(
    address: str,
    depth: int = Query(1, ge=1, le=2),
    max_nodes: int = Query(120, ge=10, le=500),
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = GraphService(neo4j)
        return service.address_subgraph(address=address, depth=depth, max_nodes=max_nodes)
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")
