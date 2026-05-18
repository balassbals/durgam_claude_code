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

**Affected pages:** `/` (home), `/change-password`, all `/admin/*` pages, `/audit`.  
**Milestone to revisit:** UI Polish (before M20).

---

## Layout

- `/change-password` and similar auth pages: nav should be at top, not vertically
  centred. Form layout needs a design pass.
- `/change-password` form looks basic/unprofessional; needs spacing and typography polish.

---

## Responsiveness

- At 360px viewport: tables don't convert to cards (Tier 1 spec in UX Charter §6
  not fully implemented in practice; the component code exists but rendering at
  narrow widths needs testing and tuning).
- At 360px: navigation cramped; hamburger drawer behaviour inconsistent at edge widths.
- At 768px (tablet): navbar layout cramped.

---

## Forms and widgets

- Permission check widget: replace raw UUID inputs with dropdowns populated from
  users, roles, and scope-objects (departments, campuses). UUIDs should not be
  visible to end users in the admin UI.
- Generally: all UUIDs in admin UIs should be hidden from users; display by name
  with internal UUID stored in the form's hidden state.

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

---

## Notification persistence

Permission-denial notifications on `/admin/*` and `/admin/config/*` redirects clear on
the same render cycle as the redirect, making them appear for < 100ms in practice.
Real users perceive this as "something flashed but I couldn't read it." The flash
lifecycle rule (cleared on next navigation, M2 pattern) is correct for preventing
notification leakage, but sacrifices readability for one-time informational messages.

**Observed at M3 Session 5:** `student_001` redirected from `/admin/config` sees an
amber permission-denial notification that disappears before it can be read.

**Proposed fix for UI Polish milestone:** implement a toast-style notification with
auto-dismiss after 3–5 seconds, independent of page navigation state. Toast queue
persists until the timer fires or the user dismisses explicitly.

Notifications that **should** use the persistent-toast pattern:
- Permission denials (informational, not destructive; user needs to read it).
- Save-success confirmations (so the user actually sees "Campus saved.").
- Login failures (already partially handled — consistency pass).

Notifications that **should keep** the current per-page-flash pattern:
- Temp password displays (Bug 8 at M2 — one-time, requires explicit Dismiss).
- Forced-flow prompts (`must_change_password` banner).
- Error states that block the page from rendering normally (inline, not toast).
