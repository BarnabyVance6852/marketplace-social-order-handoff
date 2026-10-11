import httpx
import json

from marketplace_auth.infrai_client import InfraiClient


def test_client_decodes_envelope_and_retries_rate_limit() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        assert request.method == "POST"
        assert request.url.path == "/v1/captcha/verify"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "widget_record_id": "widget-123",
            "token": "captcha-token",
            "action": "order_handoff",
        }
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0.5"},
                json={
                    "ok": False,
                    "data": None,
                    "error": {"code": "RATE_LIMITED", "message": "retry later"},
                    "metadata": {},
                },
            )
        return httpx.Response(
            200,
            json={"ok": True, "data": {"valid": True}, "error": None, "metadata": {}},
        )

    client = InfraiClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        sleep=delays.append,
    )
    try:
        result = client.verify_captcha("captcha-token", action="order_handoff", widget_record_id="widget-123")
    finally:
        client.close()

    assert result == {"valid": True}
    assert attempts == 2
    assert delays == [0.5]
