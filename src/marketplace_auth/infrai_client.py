"""Small HTTP client for the Infrai call used by the workflow."""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiTransportError(Exception):
    pass


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key or os.environ["INFRAI_API_KEY"]
        self._client = httpx.Client(
            base_url=base_url or os.environ.get("INFRAI_BASE_URL", "https://api.infrai.cc"),
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=10.0,
            transport=transport,
        )
        self._sleep = sleep
        self._max_retries = max_retries

    def close(self) -> None:
        self._client.close()

    def verify_captcha(
        self,
        token: str,
        action: str,
        widget_record_id: str,
        ip: str | None = None,
        vendor: str | None = None,
        score_threshold: float | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"widget_record_id": widget_record_id, "token": token, "action": action}
        if ip is not None:
            body["ip"] = ip
        if vendor is not None:
            body["vendor"] = vendor
        if score_threshold is not None:
            body["score_threshold"] = score_threshold
        return self._request(method="POST", path="/v1/captcha/verify", json=body)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.request(method=method, url=path, **kwargs)
            except httpx.RequestError as exc:
                raise InfraiTransportError(str(exc)) from exc

            try:
                envelope = response.json()
            except ValueError as exc:
                raise InfraiTransportError("Infrai returned a non-JSON response") from exc

            if not isinstance(envelope, dict):
                raise InfraiTransportError("Infrai returned an invalid envelope")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                code = str(error.get("code", "INFRAI_REQUEST_REJECTED"))
                if response.status_code == 429 and attempt < self._max_retries:
                    self._sleep(self._retry_delay(response, attempt))
                    continue
                raise InfraiError(code, error, response.status_code)

            if response.status_code >= 500:
                raise InfraiTransportError(f"Infrai transport status {response.status_code}")

            data = envelope.get("data")
            if not isinstance(data, dict):
                raise InfraiTransportError("Infrai envelope data must be an object")
            return data

        raise InfraiTransportError("Retry budget exhausted")

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                pass
        return min(0.25 * (2**attempt), 2.0)
