# Security Decisions Log

This file records deliberate security design decisions made during DURGAM development.
Each entry explains the decision, the alternatives considered, the residual risk, the
compensating controls, and the conditions under which the decision should be re-evaluated.
The intent is that future auditors can see these decisions were considered and not overlooked.

**Date format:** YYYY-MM-DD throughout this file. SD-003 onward must use the same format.

---

## SD-001 — Session storage model: rx.Cookie() with opaque token (Path A)

**Milestone:** M1 — Authentication  
**Date:** 2026-05-12  
**Decision makers:** Project architect (recorded via OQ-9 verification process)

### Context

RFP §6.1 requires: "Session: signed, HTTP-only, Secure, SameSite=Lax cookie; 7-day
sliding inactivity expiry."

Reflex 0.9.2 stores its CLIENT_TOKEN in `window.sessionStorage` (not an HTTP cookie)
and offers `rx.Cookie()` as the only state-var cookie API. Cookies set via `rx.Cookie()`
are written by the JavaScript `universal-cookie` library; the `HttpOnly` flag cannot
be set by JavaScript. See `docs/tech_debt.md` → TD-005 for the full technical analysis.

### Decision

**Path A chosen:** Store an opaque server-generated UUID v4 session token in an
`rx.Cookie()` with the following settings:

```python
session_token: str = rx.Cookie(
    name="dsession",
    same_site="lax",
    secure=True,
    max_age=7 * 24 * 3600,
    path="/",
)
```

The token maps to `UserSession` in the database (which holds `user_id`, `expires_at`,
`last_active_at`, `is_invalidated`). Server-side invalidation is authoritative: even
if an attacker holds the cookie value, a logged-out or admin-revoked session is rejected.
Sliding expiry: `max_age` is refreshed on every authenticated request and
`UserSession.last_active_at` is updated.

### Alternatives considered

**Path B — Custom Starlette middleware for real HttpOnly cookie:**  
Reflex's Starlette base accepts `api_transformer` callables. A middleware could intercept
the initial HTTP response and set a `Set-Cookie: dsession=...; HttpOnly; Secure; SameSite=Lax`
header. The WebSocket upgrade handler would then read this cookie to populate
`current_user_id`. This fully meets §6.1 but requires a non-trivial hybrid
HTTP+WebSocket session handshake, a custom Starlette route outside the Reflex page model,
and ongoing maintenance as Reflex evolves. Path B remains available as an escalation path.

### Residual risk

An XSS vulnerability anywhere in DURGAM could read `document.cookie` and steal the
session token.

### Compensating controls

1. Token is opaque (UUID v4, not the user's UUID or any PII).
2. `SameSite=Lax` blocks cross-site request forgery via cookie injection.
3. `Secure=True` ensures the cookie is only sent over HTTPS in production.
4. React's JSX engine HTML-escapes all rendered values by default.
5. CLAUDE.md prohibits `rx.html()` with user-controlled strings; CI lint enforces.
6. All user-supplied content is rendered through Reflex component primitives.

### Escalation triggers

- Reflex 1.0+ ships a server-side `HttpOnly` cookie API.
- M20 security hardening review determines the residual risk is unacceptable.
- An XSS surface is discovered anywhere in DURGAM.
- A penetration test is conducted before production launch.

### Pre-production requirement

Before any production deployment, SD-001 must be explicitly re-evaluated and
signed off by the system administrator as part of the M20 hardening milestone.

---

## SD-002 — Framework choice: Reflex retained despite §6.1 cookie-model mismatch

**Milestone:** M1 — Authentication  
**Date:** 2026-05-12  
**Decision makers:** Project architect (recorded via OQ-9 verification process)

### Context

During OQ-9 verification it was confirmed that Reflex 0.9.2's session model uses
`sessionStorage` rather than an HTTP cookie. This creates a structural gap against
RFP §6.1's HttpOnly requirement (detailed in SD-001).

### Decision

**Retain Reflex at M1.** The gap is mitigable with the compensating controls in SD-001.
The cost of switching to an alternative framework (FastAPI + Jinja2, Django, etc.) would
require rewriting the entire M0 foundation. Path B (Starlette middleware) exists as an
incremental upgrade path that does not require a framework switch.

This decision is recorded deliberately so that it is visible to future auditors. The
gap was identified, analysed, and accepted with compensating controls — it was not
overlooked.

### Escalation triggers

- A critical XSS vulnerability is discovered in DURGAM.
- Reflex 1.0+ ships a server-side cookie API (at which point SD-001 becomes moot and
  this decision is vindicated).
- A security audit or penetration test classifies the residual risk as unacceptable.
- The M20 hardening review determines that compensating controls are insufficient to meet
  the OWASP ASVS Level 2 baseline (§6) before production launch.

### Pre-production requirement

SD-001 and SD-002 must both be reviewed and signed off in the M20 hardening milestone.

---

## SD-003 — File download endpoint uses a permissive default with purpose-based escalation

**Milestone:** M5a — Configuration — Identity Attachments
**Date:** 2026-05-24
**Decision makers:** Project architect

### Context

The authenticated file download endpoint (`/api/files/{file_id}`) serves all
`FileAsset` rows. Some file types are restricted by §9.3 (letterheads are
"not directly visible" outside Registrar family + SysAdmin; templates are
IQAC-only). Others (future exports, generic attachments) should be
downloadable by any authenticated user.

### Decision

**Permissive default with explicit escalation.** The endpoint checks
`file_asset:read:*` (granted to all authenticated users via `_PUBLIC_READ`)
as the baseline. When `FileAsset.purpose` matches a key in
`_PURPOSE_PERMISSION_MAP`, the endpoint requires the resource-specific
`read` permission instead (e.g., `letterhead_asset:read` for
`purpose="letterhead"`).

The map at M5a:
```python
_PURPOSE_PERMISSION_MAP = {
    "letterhead": "letterhead_asset",
    "template": "template_asset",
}
```

### Why the default is inverted (permissive, not restrictive)

Most file types in DURGAM (exports, calendar ICS files, generic
attachments) should be downloadable by any authenticated user. A restrictive
default (`deny unless purpose is in an allow-list`) would require updating
the allow-list for every new file type — an easy omission that silently
blocks legitimate downloads. A permissive default with explicit restrictions
for known-sensitive types matches the actual access pattern.

### Residual risk

A future milestone introduces a restricted file purpose (e.g., exam
materials, confidential HR attachments) but forgets to add it to
`_PURPOSE_PERMISSION_MAP`. The file would be downloadable by any
authenticated user who knows the UUID.

### Compensating controls

1. UUIDs are non-guessable (v4, 122 bits of entropy).
2. The UI for restricted pages is permission-gated — users never see
   file IDs they shouldn't have.
3. The `purpose` field is set server-side by the service layer — users
   cannot forge it.

### Escalation triggers

- M20 hardening: audit all `purpose` values in the `file_assets` table
  against `_PURPOSE_PERMISSION_MAP`. Any purpose that represents a
  restricted file type must have an entry.
- Any new module that uploads files with access restrictions must add
  its purpose to the map as part of the module's PR.
- If the number of restricted purposes grows large, consider inverting
  the default (deny-unless-allowed) with an explicit allow-list for
  public file types.
