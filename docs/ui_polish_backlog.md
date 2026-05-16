# UI Polish Backlog

Items deferred to the dedicated UI Polish milestone (before M20) or noted as
acceptable trade-offs for v1. See UX Charter §10 for the formal deferral policy.

---

## Blank-screen flicker before redirect to /login

**Context:** The route-protection pattern (established M1/M2) shows a blank
screen (`rx.fragment()`) before redirecting unauthenticated users to `/login`.
This is intentional: it prevents admin or home-page chrome from flashing before
the redirect fires.

At extremely fast LAN speeds the blank-to-redirect transition may be perceived
as a flicker (visible for <100ms). At throttled speeds (Slow 3G) it shows a
blank screen which is clearly intentional.

**Decision:** Acceptable for v1. Revisit in the UI Polish milestone if user
research identifies it as a friction point. A server-side redirect (via Reflex's
`api_transformer` or a pre-render hook) would eliminate it entirely but requires
non-trivial framework integration (documented in docs/security_decisions.md →
SD-002 Path B escalation path).

**Affected pages:** `/` (home), `/change-password`, all `/admin/*` pages.  
**Milestone to revisit:** UI Polish (before M20).

---

## Spacing / typography / component sizing

Per UX Charter §10: spacing scale, type scale, and component sizing tokens are
deferred to the UI Polish milestone. Components use Reflex defaults with the M0
colour palette. Inconsistency across modules during M2–M15 is acceptable.

---

## Mobile drawer animation

The hamburger drawer (required from M2) uses Reflex's built-in `rx.drawer`
which has a slide animation. The animation duration and easing are default
Reflex values. Custom animation tuning deferred to UI Polish milestone.
