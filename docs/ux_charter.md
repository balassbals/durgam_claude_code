# DURGAM UX Charter

This document establishes the front-end standards every page of DURGAM
must satisfy. It complements the RFP (which specifies *what* the system
does) by specifying *how it feels to use*.

The RFP is read by Claude Code as a contract. This charter is read
by the engineer, the agent, and the administrator together. Every
standard below is enforceable: either by automated check, by manual
ritual at the milestone gate, or both.

## How this document grows

DURGAM is built over 20 milestones. The UI evolves with the modules:

- **M0**: theme tokens established, no user flows.
- **M1**: authentication shell — logout, change-password reachable from
  the home page. The home page is a minimal placeholder showing the
  theme.
- **M2**: Admin module — sys_admin now has destinations, so the
  navigation shell gains its first real entries.
- **M3–M15**: each module adds its own navigation entries to the shell,
  scoped to roles that can use it.
- **M16**: per-role dashboards replace the home page placeholder.
- **A dedicated UI Polish milestone before M20**: a focused pass
  applying full design tokens (spacing, type, component sizing) to
  every page, retrofitting visual quality after functional scope is
  complete.
- **M20**: hardening; accessibility audit, final theme polish, sign-off.

This charter is the floor every milestone must satisfy. Visual polish
beyond the floor is concentrated in the UI Polish milestone.

## 1. Application shell

Every authenticated page must include:

- A **persistent header** with: the institutional name; the active
  user's identity ("Logged in as: {username}"); and the active role
  context when the user holds multiple roles.
- A **logout control** reachable without scrolling on every page.
- A link to **"My account"** providing access to: change password,
  view profile (when profile module ships), view active sessions
  (when admin module ships).
- A **notifications bell** showing unread count, opening the in-app
  notification inbox (when notification module ships).

Every page includes a footer with the institutional name and the
current academic-year context (e.g. "AY 2025-26").

Unauthenticated pages (login, forgot-password, reset-password) carry
a simplified header showing only the institutional name and a "Back
to login" link where appropriate.

At M1, the header contains "Logged in as: {username}", a logout
button, and a change-password link. Notification bell and "My account"
menu structure appear at the milestones that introduce their
underlying features.

## 2. Navigation pattern

Navigation is **role-driven**. A user with N roles sees N navigation
groups, deduplicated. The agent must not hand-code per-role navigation;
it is composed from a registry that each module contributes to.

**No page in the system is reachable only by URL.** Every page has at
least one navigable path from the user's dashboard or a sidebar entry.
If a feature exists, a user must be able to find it without typing
into the address bar.

The agent must add at least one Playwright scenario per module that
starts at `/` and navigates to the feature the way a real user would.
URL-based scenarios verify pages work when reached; UI-based scenarios
verify pages are reachable.

This is the Navigation Reachability rule captured in CLAUDE.md.

## 3. Forced flows and interstitials

Any user state that requires immediate action produces an
**interstitial** that blocks normal navigation until resolved:

- `must_change_password=true` → redirect to `/change-password`; user
  cannot reach any other authenticated page until the change is made.
- `profile_completed=false` (Faculty, Student) → banner on `/`
  directing to profile-completion form; the form is the only
  navigable target besides logout. (Applies from the milestone that
  introduces profile completion.)
- Pending forced re-acknowledgement at AY rollover (future).

Interstitials always explain what is required and why. They never
trap the user without explanation.

## 4. Confirmation patterns

**Destructive actions** show a confirmation dialog that:
- Names the affected resource ("Delete user 'jdoe'?").
- States the consequence in plain language ("This will deactivate
  the account. The user can no longer log in.").
- Offers a clear cancel button.

**Non-destructive actions** never show a confirmation. Don't ask
"are you sure" before normal saves.

## 5. Loading, empty, and error states

Every list view has:
- A **loading skeleton** that renders within 250ms while data loads.
- An **empty state** with a clear call-to-action when no records
  exist ("No courses yet. Create your first course →").
- An **error state** with a recovery suggestion when loading fails
  ("Couldn't load courses. Retry?").

Forms always show inline validation errors next to the offending
field, not in a single error bar at the top.

## 6. Responsiveness contract

Every page must render and be usable at:
- **360px** (small mobile)
- **768px** (tablet — navigation collapses to drawer)
- **1280px** (laptop)
- **1920px** (desktop)

"Usable" means: every action reachable; no horizontal scroll; no
overlapping text; tap targets at least 44px on touch widths.

The navigation collapses to a hamburger drawer below 768px. The
drawer contains the same items as the desktop navigation, organised
the same way.

## 7. Theme consistency

**No component hard-codes color, font, or spacing.** All design
tokens flow from `ThemeContext`. The single committed theme is
Puttaparthi Saffron–Indigo–Ivory, defined in §15 of the RFP.

A CI check scans component files for hex literals (`#RRGGBB`) and
bare pixel values; if found in component code outside `theme.py`,
the build fails.

## 8. Accessibility floor

- Every page passes axe-core with **zero critical violations**.
- Every interactive element has a **visible focus indicator**.
- Every form field has a **label** (visible or aria-labelled).
- Color is never the only signal — error states show an icon and
  text, not just red.
- Tab order follows visual order; no `tabindex` greater than 0.

## 9. Elegance as a stop-condition

When a page looks busy, the first move is **removal**, not addition.
White space is a feature. Lists should breathe. Headings should be
sparing.

Three defaults:
- Single primary action per page; secondary actions get less visual
  weight.
- One heading level per hierarchy step (`h1` once, `h2` for sections).
- Tables dense enough to show many rows without scrolling, but never
  so dense that rows touch.

## 10. Design tokens — current and deferred

At M1, the binding tokens are the **color tokens** from RFP §15.1:
indigo, saffron, ivory, slate, muted, gold.

**Spacing scale, type scale, and component sizing tokens** are
deferred to the UI Polish milestone scheduled before M20. Until then,
components use Reflex defaults with the color palette applied.
Inconsistency in spacing and typography across modules is acceptable
during M2–M15; the UI Polish milestone will retrofit all pages
against a single design-tokens system at once.

This is a deliberate trade-off: shipping functional modules quickly
through M2–M15 is more valuable than perfecting visual coherence
along the way. The retrofit at the polish milestone is cheaper than
re-polishing after every functional milestone.

## 11. The UX gate ritual

Every milestone gate is supplemented by a UX gate:

- The administrator manually uses the application as each role the
  milestone touches, completing the milestone's named flows using
  only UI navigation, at three viewport widths (360px, 768px, 1280px).
- The administrator checks each item in this charter that applies
  to the milestone.
- The milestone closes only when both the functional gate clauses
  AND the UX charter checks pass.

The detailed ritual is in `docs/prompts/gate_verification.md`.

## 12. What this charter does not require yet

To prevent over-scoping at each milestone, the following are
explicitly **not** required until their named milestone:

- Per-role dashboards with widgets: M16.
- Notification bell with unread count: the milestone that introduces
  the notification module.
- "My account" sub-pages beyond change-password: the milestone that
  introduces profile management.
- Full design-tokens pass (spacing, type, component sizing): the
  UI Polish milestone before M20.
- axe-core CI integration: M20 hardening.
- Mobile drawer navigation: required from M2 when navigation has
  more than two entries.

A milestone is not failing the charter by deferring items that
belong to a later milestone. Apply the charter to what the milestone
introduces; trust that later milestones handle what is theirs.

## 13. Principles confirmed at M5b

1. **Render-after-confirm for forms with uploads.** Forms that involve file uploads stage the file selections in state and persist everything (record + files) in a single save action. No auto-save on file selection. Pattern reference: counsellor and non-regular faculty pages.

2. **Live-sourced role pickers everywhere.** All role-code fields read the roles table at render time. No hardcoded role enums in UI components. New roles added through admin appear in pickers automatically.

3. **Permission visibility matches capability.** If a user can't perform an action, they don't see the UI affordance for it. Applied to: bulk-import tabs, kebab menu items, back-links, confirmation buttons. Defense-in-depth — backend checks still reject unauthorized actions even when UI hides the affordance.

4. **Downloads via rx.link, not rx.download.** rx.download has strict URL validation that doesn't accept cross-origin URLs. Kebab download items use rx.link href={DOWNLOAD_PREFIX + path}. Pattern reference: letterheads.py and templates.py.

5. **User-facing flash for silent infrastructure failures.** When a docgen template has no placeholders and the export "succeeds" with the unmodified template, surface a clear user-facing warning explaining what happened and how to fix it. Pattern reference: counsellor and faculty-mentor exports.

6. **Scope-aware displays.** Scoped roles render as "{role} ({scope label})" — e.g. "Dean (SCI — Sciences)" not just "DEAN". Use the shared scope-label resolver in durgam/scopes/registry.py. Apply uniformly across calendar owner_role displays, role-email scope columns, etc.

7. **Pending/Approved badge for entities with approval workflow.** Non-regular faculty appears as "Pending" until approved; "Approved (by Director Name, on date)" after. Make the state visible at-a-glance in listings.

## 14. Principles confirmed at M8

1. **"As per approval" for non-balance leave types.** Leave types that carry no running balance (SCL — Special Casual Leave, EOL — Extra Ordinary Leave, SL — Study Leave) display an "As per approval" badge in balance cards instead of a numeric balance. A supporting caption reads "Granted on a case-by-case basis — no running balance." Never show a 0-balance card for these types — zero is misleading when the leave is discretionary. Pattern reference: `durgam/pages/leave/my_leave.py` `_balance_card()`.

2. **In-flight progress always visible, not hidden in a table column.** Leave requests in-flight render as custom rows (not a data_table) with a dedicated progress text line beneath the request summary. This ensures progress context is visible on both desktop and mobile — a `hidden_on_card=True` column collapses on mobile and was confirmed unsuitable. Pattern: `_in_flight_row()` in `my_leave.py`.

3. **History terminal state as a single summary sentence.** Terminal leave requests (approved, rejected, cancelled, withdrawn) show a one-sentence outcome in the history list: who decided, when, any comment (truncated at 60 chars), and the stage of the total. Avoids full approval timeline in the list; the detail page holds the full record. Pattern: `_build_leave_history_summary()` in `durgam/states/leave_request.py`.

4. **Approval detail page: balance card visible for requestor's leave type only.** On the approval detail page (`/approvals/request/[id]`), do not show a balance card for the CURRENT USER's balance. Show only the requestor's balance (or suppress for non-balance types). Showing the approver's own balance is misleading and was confirmed a UX defect in gate walkthrough (E-022). Pattern reference: `_load_leave_detail` in `durgam/states/approval_requests.py`.

## §15 M8.1 — Leave Module Follow-ups UX Principles

### 1. Post-facto application badge

When a leave request's `starts_on` is before today, an amber informational badge is rendered inside the Apply modal above the submit button:

> "Post-facto application — this request covers past dates."

The badge uses amber styling (`color_scheme="amber"` / `flash_warning()` token). It is **informational only** — it does not block submission. The admin and approver see a "Post-facto" badge on the in-flight row and in the approval detail panel.

Pattern reference: `durgam/pages/leave/my_leave.py` `_apply_modal()` and `durgam/pages/admin/leave_request_edit.py`.

### 2. Withdraw-reason modal (post-approval withdrawal)

The "Withdraw (post-approval)" action on in-flight approved-leave rows opens a modal requiring a reason of at least 10 characters. The Confirm button is disabled (opacity 0.5, `disabled=True`) while `len(withdraw_reason.strip()) < 10`. This is enforced via a computed var (`is_withdraw_valid`), NOT a service-layer length check — the service check is defense-in-depth, not the primary UX gate.

The action is labeled **"Withdraw (post-approval)"** to distinguish it from the pre-approval "Withdraw" action that cancels an in-flight request. Both actions can coexist on the same row if the leave is in `"in_review"` (pre-approval only) or `"approved"` (post-approval only).

### 3. Two-stage CSV import preview

Import flows with a potentially destructive overwrite (balance import) use a mandatory two-stage preview:

1. **Stage 1 — Preview:** Upload CSV → server resolves AY, validates rows, returns preview with:
   - Resolved AY name displayed prominently at the top (e.g. "Importing into AY: 2025-26").
   - Valid rows table: shows what will be upserted.
   - Invalid rows table (if any): shows row number + reason.
   - Commit button **disabled** while any invalid rows are present OR no unlocked AY exists.
2. **Stage 2 — Commit:** Admin explicitly clicks Commit → all valid rows upserted, audit trail written, success flash with row count.

Commit button must never be enabled on a preview with errors. AY resolution failure must surface a clear "No active AY found — configure or unlock an AY before importing" message.

### 4. Admin state transitions — dropdown defense in depth

The leave request admin edit modal's "New State" dropdown lists only valid transitions for the current state (computed var `allowed_new_states_filtered`). The Save button is disabled when the selection is empty or invalid (computed var `is_save_valid`). The service layer enforces the same rules independently. Neither layer alone is sufficient — both are required.

### 5. Window-elapsed gate on approved-leave admin transitions

When an admin opens the edit modal for an approved leave whose `ends_on < today`:

- The "New State" dropdown is **disabled** with no options.
- An amber informational banner explains the constraint and redirects to `/admin/leave/balance-edit`.
- The Save button remains disabled.

This prevents a confusing UX where the admin selects a transition, submits, and receives a service-layer error with no visible feedback. The UI communicates the constraint before any server round-trip.

Pattern reference: `durgam/states/leave_request_admin.py` `edit_window_elapsed` and `allowed_new_states_filtered`; `durgam/pages/admin/leave_request_edit.py` `_edit_modal()`.

---

## M9 Announcements — UX conventions

### 1. Status badges on announcements

Three mutually exclusive status badges, applied in priority order (first match wins):

| Status | Badge text | Radix color_scheme | variant | Condition |
|--------|-----------|-------------------|---------|-----------|
| Withdrawn | "Withdrawn" | `gray` | `outline` | `is_deleted = True` |
| Pending | "Pending" | `amber` | `soft` | `scheduled_at > NOW()` and not withdrawn |
| (none) | — | — | — | Published and not withdrawn |

The badge appears in both the browse-list row card and the detail panel metadata row. An announcement cannot be both Withdrawn and Pending (withdraw is blocked after the window closes; if it was withdrawn during the window, it's Withdrawn).

### 2. Withdraw button gating

The "Withdraw" destructive button in the detail panel renders only when `can_withdraw = True`:

```python
can_withdraw = is_pending and not is_deleted
```

`is_pending` is computed at state load time (server-side). The client does not re-check the window boundary in real time. If a user keeps a detail panel open across the window boundary, they will see the Withdraw button until they next open the panel. This is acceptable for M9 — a stale UI state shows the button but the service rejects the action with "Announcement is already published."

For a future UI-polish pass: show a countdown timer and disable the button client-side when the deadline passes (requires a `rx.moment` or similar component — deferred to UI Polish milestone).

### 3. Pending window UX in category admin

The Withdraw Window field in `/admin/config/announcement-categories` is labeled "Withdraw Window (seconds)" with a helper text: "Seconds after composing during which the announcement is pending (invisible to recipients but withdrawable). 0 = publish immediately." The input is a number field, min=0, max=86400.

For admin convenience: the category list page does not show the delay value in the table (too low information density). It is only visible on the edit modal. If admins need to scan delays, direct SQL is the recommended approach for M9.
