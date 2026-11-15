from fastapi import Request

from api.neo4j_service import Neo4jService
from api.services.alert_service import AlertService
from api.services.address_service import AddressService


def get_neo4j(request: Request) -> Neo4jService:
    return request.app.state.neo4j


def get_alert_service(request: Request) -> AlertService:
    return AlertService(request.app.state.neo4j)


def get_address_service(request: Request) -> AddressService:
    return AddressService(request.app.state.neo4j)

