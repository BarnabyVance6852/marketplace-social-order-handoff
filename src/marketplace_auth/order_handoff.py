"""Domain decision for releasing seller assets to a buyer."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from urllib.parse import urlencode

from pydantic import BaseModel, Field, HttpUrl


class CapabilityClient(Protocol):
    def verify_captcha(
        self,
        token: str,
        action: str,
        widget_record_id: str,
        ip: str | None = None,
        vendor: str | None = None,
        score_threshold: float | None = None,
    ) -> dict[str, object]:
        """Return the captcha verification payload."""


class LoginStart(BaseModel):
    provider: str = Field(pattern="^(google|github)$")
    return_to: HttpUrl
    redirect_uri: HttpUrl


class LoginStartResult(BaseModel):
    authorization_url: str
    login_state: str
    provider: str


class OrderHandoff(BaseModel):
    order_id: str = Field(min_length=1)
    seller_id: str = Field(min_length=1)
    buyer_id: str = Field(min_length=1)
    asset_ids: list[str] = Field(min_length=1)
    buyer_update: str = Field(min_length=1)
    login_state: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)
    widget_record_id: str = Field(min_length=1)


class HandoffResult(BaseModel):
    order_id: str
    seller_id: str
    buyer_id: str
    asset_ids: list[str]
    buyer_update: str
    provider: str
    status: str


@dataclass(frozen=True)
class PendingLogin:
    provider: str
    return_to: str


class LoginStateStore:
    def __init__(self) -> None:
        self._pending: dict[str, PendingLogin] = {}
        self._lock = Lock()

    def add(self, state: str, login: PendingLogin) -> None:
        with self._lock:
            self._pending[state] = login

    def consume(self, state: str) -> PendingLogin | None:
        with self._lock:
            return self._pending.pop(state, None)


class InvalidLoginState(Exception):
    pass


class MarketplaceHandoff:
    def __init__(
        self,
        client: CapabilityClient,
        states: LoginStateStore | None = None,
        oauth_client_ids: dict[str, str] | None = None,
    ) -> None:
        self._client = client
        self._states = states or LoginStateStore()
        self._oauth_client_ids = oauth_client_ids

    def start_login(self, request: LoginStart) -> LoginStartResult:
        state = secrets.token_urlsafe(24)
        client_id = self._oauth_client_id(request.provider)
        endpoint, scope = _OAUTH_PROVIDERS[request.provider]
        parameters = {
            "client_id": client_id,
            "redirect_uri": str(request.redirect_uri),
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
        authorization_url = f"{endpoint}?{urlencode(parameters)}"
        self._states.add(
            state,
            PendingLogin(provider=request.provider, return_to=str(request.return_to)),
        )
        return LoginStartResult(
            authorization_url=authorization_url,
            login_state=state,
            provider=request.provider,
        )

    def _oauth_client_id(self, provider: str) -> str:
        if self._oauth_client_ids is not None:
            return self._oauth_client_ids[provider]
        return os.environ[f"{provider.upper()}_OAUTH_CLIENT_ID"]

    def release_order(self, request: OrderHandoff, ip: str | None = None) -> HandoffResult:
        pending = self._states.consume(request.login_state)
        if pending is None:
            raise InvalidLoginState("login_state is unknown or already consumed")

        try:
            self._client.verify_captcha(
                token=request.captcha_token,
                action="order_handoff",
                widget_record_id=request.widget_record_id,
                ip=ip,
            )
        except Exception:
            self._states.add(request.login_state, pending)
            raise

        return HandoffResult(
            order_id=request.order_id,
            seller_id=request.seller_id,
            buyer_id=request.buyer_id,
            asset_ids=request.asset_ids,
            buyer_update=request.buyer_update,
            provider=pending.provider,
            status="ready_for_handoff",
        )


_OAUTH_PROVIDERS = {
    "google": ("https://accounts.google.com/o/oauth2/v2/auth", "openid email profile"),
    "github": ("https://github.com/login/oauth/authorize", "read:user user:email"),
}
