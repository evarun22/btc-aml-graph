import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.neo4j_service import Neo4jService
from api.routes import health, kpis, addresses, alerts, entities, ofac, graph

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    neo4j = Neo4jService(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
        database=settings.neo4j_database,
    )

    try:
        neo4j.connect()
        logger.info("Neo4j connected")
    except Exception as exc:
        logger.warning("Neo4j not available at startup: %s", exc)

    app.state.neo4j = neo4j
    yield
    neo4j.close()


settings = get_settings()

app = FastAPI(
    title="Bitcoin AML Graph API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(kpis.router)
app.include_router(addresses.router)
app.include_router(alerts.router)
app.include_router(entities.router)
app.include_router(ofac.router)
app.include_router(graph.router)
