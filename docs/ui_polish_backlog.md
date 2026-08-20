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

---

## M8 Leave Rules — polish backlog

### E-018: Leave sanction matrix — CRUD dropdowns need pagination (defer to UI Polish)

The `LeaveSanctionAuthorityRule` admin CRUD form loads all roles and departments as
dropdown options. With 20+ roles and 30+ departments this is manageable, but will become
slow at real-institution scale. Proposed fix: replace flat `<select>` with a searchable
combobox for role/department pickers in the matrix editor. Deferred to UI Polish milestone
as the current dropdowns function correctly.

**Filed:** E-018 in `docs/rfp_errata.md`.

### In-flight leave request rows — visual polish

The `_in_flight_row()` component (`durgam/pages/leave/my_leave.py`) uses a plain
`rx.box` with a border for each in-flight request. For UI Polish milestone:

- Add a left-border color accent matching the leave-type color (CL = green, EL = blue,
  SCL = amber, etc.) to make type scannable at-a-glance.
- Consider a subtle "pulsing" or "active" indicator for the stage badge.
- The progress text line (`Progress: Stage X of Y — Awaiting ROLE`) uses default font
  size (`0.8rem`). Consider matching the approved palette card style with a muted chip
  rather than plain text.

**Observed at M8 Phase 8.4 gate walkthrough.** Current state is functional; polish
deferred to UI Polish milestone.

---

## M8.1 Leave Follow-ups — polish backlog

### UI-POLISH-M8.1-01 — Sticky first column on /admin/leave/balance-edit

Deferred from M8.1 Phase 7. Two attempts failed to lock the username column during horizontal scroll:

- **Phase 7.1** (`8953fdd`): `position: sticky; left: 0` with `overflow_x="auto"` on the outer wrapper. The sticky behaviour did not activate — the column scrolled with the rest of the table.
- **Phase 7.2** (`6be2ef5`): `border_collapse: separate; overflow_x: auto` on the `rx.table.root` wrapper. Same result — column was not pinned.

Likely root cause: interaction between Radix UI `Table.Root` internals and a parent `overflow` ancestor that was not identified. The table uses Radix's scoped CSS which may reset stacking context in a way that prevents `position: sticky` from taking effect on `<th>` / `<td>` elements.

**Impact:** Purely visual. The table is functional; users must scroll left to see the username after scrolling right. No data or action is blocked.

**Proposed fix for UI Polish milestone:** Replace `rx.table` with a plain HTML table rendered via `rx.el.table` (non-Radix) for this specific page, where `position: sticky; left: 0; z-index: 1; background: var(--color-background)` on the first cell is reliable. Alternatively, use a CSS Grid layout for the table body rows so the first column can be independently overflow-hidden.

---

## M9 Announcement Module — polish backlog

### UI-POLISH-M9-01 — Withdraw window countdown timer

The detail panel shows a "Withdraw" button while `can_withdraw = True`. If the user leaves the panel open across the window boundary, the button remains visible but the service will reject the action. A live countdown timer ("Withdraw window closes in 14:23") with a client-side disable at T=0 would prevent the confusing rejected-action UX.

**Deferred to UI Polish milestone.** Requires either a `rx.moment`-style countdown component or a periodic WebSocket ping from the server. Neither pattern is established in the codebase.

### UI-POLISH-M9-02 — Multi-file attachments per announcement

The spec and Phase 8b shipped one attachment per announcement (UI-only limit; service has no count guard — TD-057). The compose form has one upload zone. A future design should consider:

- Drag-and-drop multi-file zone (up to N files, N configurable via a category setting or a global config row)
- Per-file remove button before save
- Preview thumbnails for images

**Deferred to a future milestone.** UI Polish milestone should address TD-057's service-layer count guard first; multi-file UI second.

### UI-POLISH-M9-03 — Publish delay display on category list page

The category config list table does not show `publish_delay_seconds`. Admins must open the edit modal to see the delay. For tables with many categories, scanning delays requires the admin to open each row. A "Delay" column (formatted as "30 min" or "Instant") would improve scanability.

**Deferred to UI Polish milestone.** Low impact for M9 (9 default categories; most have delay=0).

### UI-POLISH-M9-04 — Per-module announcement surfacing

The informal requirement says "Announcement meant for them should come to their module or page." M9 ships: (a) `/announcements` dedicated page, (b) dashboard widget (top 3). Surfacing announcements within other module pages (e.g., in the leave module header) is deferred.

**Target: M15 (Role-based dashboards).** See coverage_matrix.md M9 deferred items.

---

## M10 Faculty Module — polish backlog

Audit-label readability for faculty FK fields (raw UUID displayed instead of a human-readable
`employee_id — Title First Last` label) was tracked as TD-087 and **resolved** at M10 Phase 13
(commit `b568d94`) — see `docs/tech_debt.md`.

No other UI polish items were deferred from M10 at gate verification. The module shipped
clean: faculty self-service profile, directory, admin directory, NRF contract-term UI, the
faculty picker rollout across 4 admin forms, bulk CSV import, and the mentor-confirmation
re-confirm banner all closed without a UI-polish carry-forward.
