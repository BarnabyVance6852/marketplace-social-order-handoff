"""HTTP boundary for marketplace login and order handoff."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from .infrai_client import InfraiClient, InfraiError, InfraiTransportError
from .order_handoff import (
    HandoffResult,
    InvalidLoginState,
    LoginStart,
    LoginStartResult,
    MarketplaceHandoff,
    OrderHandoff,
)


def create_service(client: InfraiClient | None = None) -> FastAPI:
    capability_client = client or InfraiClient()
    workflow = MarketplaceHandoff(capability_client)
    service = FastAPI(title="Marketplace social handoff")

    @service.post("/login/start", response_model=LoginStartResult)
    def start_login(body: LoginStart) -> LoginStartResult:
        try:
            return workflow.start_login(body)
        except InfraiError as exc:
            raise HTTPException(
                status_code=_client_status(exc.status_code),
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        except InfraiTransportError as exc:
            raise HTTPException(status_code=502, detail={"code": "UPSTREAM_ERROR"}) from exc

    @service.post("/orders/handoff", response_model=HandoffResult)
    def handoff(body: OrderHandoff, request: Request) -> HandoffResult:
        try:
            ip = request.client.host if request.client else None
            return workflow.release_order(body, ip=ip)
        except InvalidLoginState as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "LOGIN_STATE_INVALID", "message": str(exc)},
            ) from exc
        except InfraiError as exc:
            raise HTTPException(
                status_code=_client_status(exc.status_code),
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        except InfraiTransportError as exc:
            raise HTTPException(status_code=502, detail={"code": "UPSTREAM_ERROR"}) from exc

    return service


def _client_status(status_code: int) -> int:
    return status_code if 400 <= status_code < 500 else 502

