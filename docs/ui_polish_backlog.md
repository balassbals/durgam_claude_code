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

## Notification persistence (RESOLVED at M3)

Resolved at M3 Session 7. Toast notification pattern implemented:
bottom-right position, 4-second auto-dismiss, X close button.
Applied to all config pages and home page. See CLAUDE.md →
"Notification pattern for config pages (M3)" for canonical implementation.

---

## Calendar — visual calendar and clash detection

- **Visual calendar** (month/week grid, drag-and-drop, colour-coded types): the M4
  calendar page uses a filtered list/table view. A richer visual calendar is a
  separate frontend task; the data model and service are reusable. See
  `docs/coverage_matrix.md` → "UI Polish Backlog — Visual Calendar (from M4)".
- **Clash detection**: deliberately NOT implemented at M4. See `docs/milestones/M4.md`
  Session 5 design decision for rationale.

---

## M5b deferrals

- Cramped horizontal config navbar — TD-007 / responsive design pass needed
- Mobile / non-WSL desktop layout polish
- Older config pages (M2/M3/M4) audit for hardcoded/free-text role fields — apply the live-sourced role-picker pattern uniformly
- Consider richer warning UX when a docgen template has no placeholders (currently a flash; might be more prominent)
- Letterhead replace flow could show preview of what's being replaced (currently just a kebab action)

---

## Permission-denied redirect notification rendering

When a non-permitted user attempts to reach an admin route (e.g.,
`student_001` typing `/admin/config`), the route guard redirects to `/`
and shows an amber notification "you do not have permission to access
this page". The redirect is correct security behaviour. The notification
UX is acceptable but not polished: the notification briefly overlaps
the landing page's content before the user re-orients to the home page.

**Observed at M3 Sessions 5–7.** User feedback during manual
verification: "looks ugly."

**Proposed fix for UI Polish milestone:** standardise the redirect
notification on the same toast pattern used for in-page success/error
notifications (bottom-right, 4-second auto-dismiss, X close). Currently
the redirect notification fires via `typed_flash()` on the home page's
render, which is a different lifecycle from the in-page toast. Unify
the rendering.
