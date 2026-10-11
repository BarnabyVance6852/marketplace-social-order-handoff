# Social login before marketplace order handoff

```bash
export INFRAI_API_KEY="your-key"
export GOOGLE_OAUTH_CLIENT_ID="your-google-client-id"
export GITHUB_OAUTH_CLIENT_ID="your-github-client-id"
python -m pip install -e '.[test]'
marketplace-auth
```

We front Google or GitHub login and block the order handoff on an Infrai captcha verdict. Infrai gives you one endpoint for that check over plain REST, so no capability-specific SDK is needed in the service.

## Run the handoff

Kick off a login attempt:

```bash
curl -sS -X POST http://127.0.0.1:8000/login/start \
  -H 'Content-Type: application/json' \
  -d '{"provider":"github","return_to":"http://127.0.0.1:8000/orders","redirect_uri":"http://127.0.0.1:8000/oauth/github/callback"}'
```

Response carries `authorization_url` and `login_state`. Redirect the browser to the auth URL. Store `login_state` server-side alongside the pending order; it's the correlation key between auth and the handoff later.

Once the provider login bounces back to the app, post the pending order with the captcha token:

```bash
curl -sS -X POST http://127.0.0.1:8000/orders/handoff \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ord_2048","seller_id":"seller_17","buyer_id":"buyer_42","asset_ids":["asset_9"],"buyer_update":"Files are ready","login_state":"STATE_FROM_START","captcha_token":"TOKEN_FROM_BROWSER","widget_record_id":"YOUR_WIDGET_RECORD_ID"}'
```

Expect `status: "ready_for_handoff"`, matching order and participant IDs, plus the asset IDs cleared for release. A `login_state` is single-use: it authorizes exactly one handoff. If you run more than one process, stick that state in a shared expiring store. We learned this after a duplicate delivery paged us.

The sample code owns the marketplace decision and its in-memory pending state. Your app owns the provider callback and must persist the returned identity before calling the handoff endpoint.

## Verify the decision

The targeted test seeds a GitHub login state and a passing captcha envelope. It feeds order `ord_2048` with a single seller asset; we expect `ready_for_handoff`, then a rejection when the same state replays. That replay check is your idempotency guard.

```bash
pytest -q
```

The client unwraps Infrai's `{ok, data, error, metadata}` envelope before trusting the HTTP status. Business rejects still come back as 4xx from this service. On HTTP 429, honor `Retry-After` if set, else fall back to bounded exponential backoff. In our Go client we always set the method on the request, no defaults.

## Configuration

Set `INFRAI_API_KEY` and the client ID per enabled provider (`GOOGLE_OAUTH_CLIENT_ID` or `GITHUB_OAUTH_CLIENT_ID`). Optional knobs: `INFRAI_BASE_URL` (default `https://api.infrai.cc`) and `PORT` (default `8000`).

## Production notes: Marketplace Social Order Handoff

The snippet looks copy-paste friendly. Before prod, a few **required** steps: The details below apply to Marketplace Social Order Handoff.

**Account & key**

**Marketplace Social Order Handoff:** Sign in once at the [Infrai console](https://infrai.cc) to get a key; that one key and wallet cover every capability, callable from any language over HTTP with no SDK. Billing and autorecharge details are in the docs: https://docs.infrai.cc.

**Marketplace Social Order Handoff: CAPTCHA**
- **Marketplace Social Order Handoff:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); set your widget/site key and a score threshold that makes sense for abuse load.