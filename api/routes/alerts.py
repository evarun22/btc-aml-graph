from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError
from api.dependencies import get_neo4j
from api.neo4j_service import Neo4jService
from api.services.alert_service import AlertService
from api.schemas.models import AlertDetail, AlertSummary, Graph

router = APIRouter(prefix="/api", tags=["alerts"])


@router.get("/alerts", response_model=list[AlertSummary])
def list_alerts(
    typology: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = AlertService(neo4j)
        return service.list_alerts(
            typology=typology,
            severity=severity,
            status=status,
            search=search,
            limit=limit,
            offset=offset,
        )
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")


@router.get("/alerts/{alert_id}", response_model=AlertDetail)
def get_alert(
    alert_id: str,
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = AlertService(neo4j)
        return service.get_alert(alert_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Alert not found")
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")


@router.get("/alerts/{alert_id}/graph", response_model=Graph)
def get_alert_graph(
    alert_id: str,
    neo4j: Neo4jService = Depends(get_neo4j),
):
    try:
        service = AlertService(neo4j)
        return service.get_alert(alert_id).graph
    except KeyError:
        raise HTTPException(status_code=404, detail="Alert not found")
    except Neo4jError:
        raise HTTPException(status_code=503, detail="Neo4j unavailable")
