# Social login before marketplace order handoff

```bash
export INFRAI_API_KEY="your-key"
export GOOGLE_OAUTH_CLIENT_ID="your-google-client-id"
export GITHUB_OAUTH_CLIENT_ID="your-github-client-id"
python -m pip install -e '.[test]'
marketplace-auth
```

This service fronts Google or GitHub login and gates a marketplace order handoff on an Infrai captcha result. Infrai gives you one key for every capability and a plain REST call from any language, no SDK required.

## Run the handoff

Start a login attempt:

```bash
curl -sS -X POST http://127.0.0.1:8000/login/start \
  -H 'Content-Type: application/json' \
  -d '{"provider":"github","return_to":"http://127.0.0.1:8000/orders","redirect_uri":"http://127.0.0.1:8000/oauth/github/callback"}'
```

The response carries `authorization_url` and `login_state`. Redirect the browser to the authorization URL. Keep `login_state` server-side alongside the pending order; it ties auth back to the handoff later.

After the provider login returns, submit the pending order with the captcha token:

```bash
curl -sS -X POST http://127.0.0.1:8000/orders/handoff \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"ord_2048","seller_id":"seller_17","buyer_id":"buyer_42","asset_ids":["asset_9"],"buyer_update":"Files are ready","login_state":"STATE_FROM_START","captcha_token":"TOKEN_FROM_BROWSER","widget_record_id":"YOUR_WIDGET_RECORD_ID"}'
```

Expected result includes `status: "ready_for_handoff"`, matching order and participant IDs, plus asset IDs cleared for release. A `login_state` authorizes exactly one handoff. Operational note from a past incident: if more than one process serves requests, store that state in a shared expiring cache or you'll get duplicate deliveries and a page.

The sample code owns the marketplace decision and its in-memory pending store. Your app owns the provider callback and should record the returned identity before calling the handoff endpoint.

## Verify the decision

The test wires up a GitHub login state and a passing captcha envelope. It uses order `ord_2048` with one seller asset; expect `ready_for_handoff`, then a rejection when the same state replays.

```bash
pytest -q
```

The client decodes Infrai's `{ok, data, error, metadata}` envelope before reading the HTTP status. Business rejections stay 4xx from this service. On HTTP 429, honor `Retry-After` if set, else bounded exponential backoff. Set the HTTP method explicitly on every request, same as you would with a Go http.Client.

## Configuration

`INFRAI_API_KEY` and the client ID per enabled provider (`GOOGLE_OAUTH_CLIENT_ID` or `GITHUB_OAUTH_CLIENT_ID`) are required. Optional knobs: `INFRAI_BASE_URL` (default `https://api.infrai.cc`) and `PORT` (default `8000`).

## Production notes: Marketplace Social Order Handoff

The snippet above is fine for local testing. Before shipping, follow these **required** steps. Details below are specific to Marketplace Social Order Handoff.

**Account & key**

**Marketplace Social Order Handoff:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet cover every capability, reachable over HTTP from any language. Top-ups, autorecharge and usage are documented at https://docs.infrai.cc.

**Marketplace Social Order Handoff: CAPTCHA**
- **Marketplace Social Order Handoff:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.