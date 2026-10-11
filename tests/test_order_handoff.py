from typing import Any

import pytest

from marketplace_auth.order_handoff import (
    InvalidLoginState,
    LoginStart,
    LoginStateStore,
    MarketplaceHandoff,
    OrderHandoff,
)


class PassingClient:
    def __init__(self) -> None:
        self.captcha_actions: list[str] = []

    def verify_captcha(
        self,
        token: str,
        action: str,
        widget_record_id: str,
        ip: str | None = None,
        vendor: str | None = None,
        score_threshold: float | None = None,
    ) -> dict[str, Any]:
        self.captcha_actions.append(action)
        return {"valid": True}


def test_social_login_state_releases_assets_once_after_captcha() -> None:
    client = PassingClient()
    workflow = MarketplaceHandoff(
        client,
        LoginStateStore(),
        oauth_client_ids={"github": "github-client-id"},
    )
    login = workflow.start_login(
        LoginStart(
            provider="github",
            return_to="https://market.example/orders",
            redirect_uri="https://market.example/oauth/github/callback",
        )
    )
    request = OrderHandoff(
        order_id="ord_2048",
        seller_id="seller_17",
        buyer_id="buyer_42",
        asset_ids=["asset_9"],
        buyer_update="Files are ready",
        login_state=login.login_state,
        captcha_token="browser-captcha-token",
        widget_record_id="widget-123",
    )

    result = workflow.release_order(request, ip="203.0.113.7")

    assert result.status == "ready_for_handoff"
    assert result.asset_ids == ["asset_9"]
    assert result.provider == "github"
    assert "github.com/login/oauth/authorize" in login.authorization_url
    assert client.captcha_actions == ["order_handoff"]
    with pytest.raises(InvalidLoginState):
        workflow.release_order(request)
