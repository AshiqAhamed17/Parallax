# Metaculus API/ToS verification — status: incomplete, needs manual check

## What was actually verified (2026-08-31, from this repo's dev environment)

**Manifold Markets — verified live, no action needed:**
```
$ curl -s -w "%{http_code}" "https://api.manifold.markets/v0/markets?limit=2"
```
Returned real market data with `HTTP 200`, no authentication, no API key. Response confirms
`"mechanism":"cpmm-1"` on every market, corroborating the CPMM architecture decision in
`implementation.md` §7.

**Metaculus — could NOT be verified from this environment:**
```
$ curl -A "Mozilla/5.0 ..." -I "https://www.metaculus.com/"
HTTP/2 403
cf-mitigated: challenge
server: cloudflare
```
Even Metaculus's plain homepage returns `403` with a Cloudflare bot-challenge header
(`cf-mitigated: challenge`) for automated/non-browser HTTP clients — this is Cloudflare blocking
the request before it reaches Metaculus's application, not necessarily Metaculus's own policy.
The `/api2/questions/` endpoint returned a `403` with body text "The API is only available to
authenticated users. Please create an account and use your API token to access the API." — this
*may* be Metaculus's real application-level response, or it may be a Cloudflare-generated block
page mimicking one. **It cannot be trusted as ground truth without a real browser session.**

## What needs to happen before Phase 7 (per the Global Constraint in `tasks.md`)

A human needs to, in a real browser:

1. Open `https://www.metaculus.com` normally and confirm the site loads (it should — the 403
   above is very likely specific to automated/headless requests, not a real outage or a
   India-specific geo-block).
2. Create a Metaculus account if one doesn't exist.
3. Look for API documentation/token generation, typically under account settings or a `/api/`
   docs page linked from the site footer or developer section.
4. Confirm: (a) does reading public question data require an API token or is some of it open?,
   (b) what does the ToS say about programmatic access/scraping/rate limits?, (c) if a token is
   required, generate one and store it as `METACULUS_API_KEY` in a local (gitignored) `.env` —
   never commit it.
5. Update this file with what was actually found, and update `implementation.md` §6-equivalent
   Metaculus section (currently deferred, since the mechanism is unknown) accordingly.

Do not proceed with Phase 7 (the Metaculus adapter) until this is done — building against an
assumed API shape risks wasted work if the real contract differs.
