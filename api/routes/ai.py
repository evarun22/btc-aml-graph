import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends

from api.schemas.models import (
    AIStatusResponse,
    ExplainAlertRequest,
    ExplainAlertResponse,
    SummarizeAddressRequest,
    SummarizeAddressResponse,
)

from api.services.ai_service import (
    ai_service,
    AIProviderUnavailableError,
    AIProviderError,
)

from api.services.alert_service import AlertService
from api.services.address_service import AddressService

from api.dependencies import (
    get_alert_service,
    get_address_service,
)

from api.utils.address_validation import validate_address as is_valid_bitcoin_address


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _to_dict(data):
    """
    Convert Pydantic models or objects to plain dicts where possible.
    """
    if data is None:
        return {}

    if hasattr(data, "model_dump"):
        return data.model_dump()

    if hasattr(data, "dict"):
        return data.dict()

    if isinstance(data, dict):
        return data

    try:
        return dict(data)
    except Exception:
        return {"value": str(data)}


@router.get("/status", response_model=AIStatusResponse)
def ai_status():
    available = ai_service.is_available()

    return AIStatusResponse(
        provider=ai_service.provider,
        available=available,
        model=ai_service.current_model(),
        message=None if available else "AI assistant is unavailable.",
    )


@router.post("/explain-alert", response_model=ExplainAlertResponse)
def explain_alert(
    request: ExplainAlertRequest,
    alert_service: AlertService = Depends(get_alert_service),
):
    alert = None

    if request.alert_id:
        try:
            alert = alert_service.get_alert(request.alert_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Alert not found")

        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

    elif request.alert:
        alert = request.alert

    else:
        raise HTTPException(
            status_code=422,
            detail="Provide either alert_id or alert object",
        )

    try:
        alert_dict = _to_dict(alert)
    except Exception:
        logger.exception("Failed to convert alert to dict")
        raise HTTPException(
            status_code=500,
            detail="Failed to prepare alert context",
        )

    if not ai_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI assistant is unavailable. Please try again later.",
        )

    try:
        explanation = ai_service.explain_alert(alert_dict)

    except AIProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    except AIProviderError:
        logger.exception("AI explain-alert provider error")
        raise HTTPException(
            status_code=502,
            detail="AI provider request failed",
        )

    except Exception:
        logger.exception("Unexpected AI explain-alert error")
        raise HTTPException(
            status_code=500,
            detail="Unexpected AI error",
        )

    alert_id = alert_dict.get("alert_id") or request.alert_id or "unknown"

    return ExplainAlertResponse(
        alert_id=str(alert_id),
        explanation=explanation,
        provider=ai_service.provider,
        model=ai_service.current_model(),
        generated_at=datetime.now(timezone.utc),
    )


@router.post("/summarize-address", response_model=SummarizeAddressResponse)
def summarize_address(
    request: SummarizeAddressRequest,
    address_service: AddressService = Depends(get_address_service),
):
    address = request.address.strip()

    validated_address = is_valid_bitcoin_address(address)

    if not validated_address:
        raise HTTPException(status_code=422, detail="Invalid Bitcoin address")

    # Use the validated/normalized address for all downstream work.
    address = validated_address

    try:
        report = address_service.get_report(address)
    except KeyError:
        report = None
    except Exception:
        logger.exception("Failed to fetch address report")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch address report",
        )

    report_dict = _to_dict(report)

    if not report_dict or not report_dict.get("exists", False):
        return SummarizeAddressResponse(
            address=address,
            exists=False,
            summary="This address is valid but was not found in the current graph.",
            provider=ai_service.provider,
            model=ai_service.current_model(),
            generated_at=datetime.now(timezone.utc),
        )

    if not ai_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="AI assistant is unavailable. Please try again later.",
        )

    try:
        summary = ai_service.summarize_address(report_dict)

    except AIProviderUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    except AIProviderError:
        logger.exception("AI summarize-address provider error")
        raise HTTPException(
            status_code=502,
            detail="AI provider request failed",
        )

    except Exception:
        logger.exception("Unexpected AI summarize-address error")
        raise HTTPException(
            status_code=500,
            detail="Unexpected AI error",
        )

    return SummarizeAddressResponse(
        address=address,
        exists=True,
        summary=summary,
        provider=ai_service.provider,
        model=ai_service.current_model(),
        generated_at=datetime.now(timezone.utc),
    )
