from fastapi import APIRouter, Depends
from api.dependencies import get_neo4j
from api.neo4j_service import Neo4jService
from api.services.kpi_service import KpiService
from api.schemas.models import Kpis, PipelineStatus

router = APIRouter(prefix="/api", tags=["kpis"])


@router.get("/kpis", response_model=Kpis)
def get_kpis(neo4j: Neo4jService = Depends(get_neo4j)):
    return KpiService(neo4j).get_kpis()


@router.get("/pipeline/status", response_model=PipelineStatus)
def get_pipeline_status(neo4j: Neo4jService = Depends(get_neo4j)):
    return KpiService(neo4j).get_pipeline_status()
