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
