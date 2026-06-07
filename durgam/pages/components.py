"""Shared page components for authenticated DURGAM pages."""

from __future__ import annotations

import reflex as rx

from durgam.states.auth import AuthState
from durgam.states.base import BaseState

# Seconds before a config-page toast notification auto-dismisses.
# Auto-dismiss is not yet implemented (requires decorated-handler changes);
# this constant is reserved for a future UI Polish milestone.
NOTIFICATION_DISPLAY_SECONDS = 4


def _nav_link(entry: dict) -> rx.Component:
    return rx.link(
        entry["label"],
        href=entry["href"],
        font_size="0.875rem",
        color="var(--color-primary)",
        font_family="var(--font-sans)",
        padding="0.25rem 0",
        text_decoration="none",
    )


def _mobile_drawer() -> rx.Component:
    """Hamburger drawer for narrow viewports (required from M2, UX Charter §12)."""
    return rx.drawer.root(
        rx.drawer.trigger(
            rx.button(
                "☰",
                background="transparent",
                border="1px solid var(--color-rule)",
                color="var(--color-body)",
                padding="0.25rem 0.5rem",
                border_radius="4px",
                cursor="pointer",
                font_size="1.1rem",
            ),
        ),
        rx.drawer.overlay(z_index="50"),
        rx.drawer.portal(
            rx.drawer.content(
                rx.vstack(
                    rx.text(
                        "DURGAM",
                        font_weight="700",
                        font_size="1.1rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                        margin_bottom="1rem",
                    ),
                    rx.foreach(
                        BaseState.visible_nav_entries,
                        _nav_link,
                    ),
                    rx.divider(margin_y="1rem"),
                    rx.link(
                        "Change password",
                        href="/change-password",
                        font_size="0.875rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                    ),
                    rx.button(
                        "Log out",
                        on_click=AuthState.logout,
                        font_size="0.875rem",
                        cursor="pointer",
                        background="transparent",
                        border="none",
                        color="var(--color-muted)",
                        padding="0",
                        font_family="var(--font-sans)",
                    ),
                    align="start",
                    padding="1.5rem",
                ),
                top="0",
                left="0",
                height="100%",
                width="min(280px, 80vw)",
                background="white",
                border_right="1px solid var(--color-rule)",
            ),
        ),
        direction="left",
    )


def nav_shell() -> rx.Component:
    """Persistent navigation bar shown on every authenticated page.

    Desktop: institutional name, nav links, username, change-password, logout.
    Mobile (≤768px): hamburger drawer + username + logout.
    """
    return rx.cond(
        AuthState.current_user_id != "",
        rx.box(
            rx.hstack(
                # Left: institutional name + nav links (desktop) OR hamburger (mobile)
                rx.hstack(
                    rx.text(
                        "DURGAM",
                        font_weight="700",
                        font_size="1rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                    ),
                    rx.hstack(
                        rx.foreach(
                            BaseState.visible_nav_entries,
                            _nav_link,
                        ),
                        gap="1.25rem",
                        display=["none", "none", "flex"],  # hidden on mobile
                        align="center",
                    ),
                    gap="1.5rem",
                    align="center",
                ),
                # Right: user info + actions
                rx.hstack(
                    rx.hstack(
                        rx.text(
                            "Logged in as: ",
                            font_size="0.875rem",
                            color="var(--color-muted)",
                            font_family="var(--font-sans)",
                        ),
                        rx.text(
                            AuthState.current_username,
                            font_size="0.875rem",
                            font_weight="600",
                            color="var(--color-body)",
                            font_family="var(--font-sans)",
                        ),
                        gap="0.25rem",
                        align="center",
                        display=["none", "flex"],  # hidden on very small screens
                    ),
                    rx.link(
                        "Change password",
                        href="/change-password",
                        font_size="0.875rem",
                        color="var(--color-primary)",
                        font_family="var(--font-sans)",
                        display=["none", "none", "block"],  # desktop only
                    ),
                    rx.button(
                        "Log out",
                        on_click=AuthState.logout,
                        font_size="0.875rem",
                        cursor="pointer",
                        background="transparent",
                        border="1px solid var(--color-rule)",
                        color="var(--color-body)",
                        padding="0.25rem 0.75rem",
                        border_radius="4px",
                        font_family="var(--font-sans)",
                    ),
                    _mobile_drawer(),
                    gap="1rem",
                    align="center",
                ),
                justify="between",
                align="center",
                width="100%",
            ),
            padding="0.5rem 1.5rem",
            background="white",
            border_bottom="1px solid var(--color-rule)",
            width="100%",
        ),
        rx.fragment(),
    )


def page_footer() -> rx.Component:
    """Footer with institutional name and academic year context."""
    return rx.box(
        rx.hstack(
            rx.text(
                "Sri Sathya Sai Institute of Higher Learning",
                font_size="0.75rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.spacer(),
            rx.text(
                "AY 2025-26",
                font_size="0.75rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            width="100%",
        ),
        padding="0.75rem 1.5rem",
        border_top="1px solid var(--color-rule)",
        background="white",
        width="100%",
        margin_top="auto",
    )


# ── Standard button helpers (Issues 6+7) ─────────────────────────────────────
# Every button in M2+ must use one of these three styles. No component
# hard-codes colors. New components in M3+ reference these helpers.

def primary_btn(*children, **props) -> rx.Component:
    """Primary action button (Save, Submit, Create, Confirm)."""
    return rx.button(
        *children,
        background="var(--color-primary)",
        color="white",
        border="none",
        padding="0.5rem 1.25rem",
        border_radius="4px",
        cursor="pointer",
        font_family="var(--font-sans)",
        **props,
    )


def secondary_btn(*children, **props) -> rx.Component:
    """Secondary action button (Cancel, Back, Close)."""
    return rx.button(
        *children,
        background="transparent",
        color="var(--color-primary)",
        border="1px solid var(--color-primary)",
        padding="0.5rem 1.25rem",
        border_radius="4px",
        cursor="pointer",
        font_family="var(--font-sans)",
        **props,
    )


def destructive_btn(*children, **props) -> rx.Component:
    """Destructive action button (Delete, Deactivate, Permanently remove)."""
    return rx.button(
        *children,
        background="var(--color-destructive)",
        color="white",
        border="none",
        padding="0.5rem 1.25rem",
        border_radius="4px",
        cursor="pointer",
        font_family="var(--font-sans)",
        **props,
    )


# ── Standard notification helpers (Issues 6+7) ───────────────────────────────

def flash_success(message: rx.Var | str) -> rx.Component:
    """Success notification box (green tint)."""
    return rx.box(
        rx.hstack(rx.text("✓", color="var(--color-success-border)"), rx.text(message),
                  gap="0.5rem", align="center"),
        background="var(--color-success-bg)",
        border="1px solid var(--color-success-border)",
        border_radius="4px",
        padding="0.75rem 1rem",
        margin_bottom="1rem",
        font_size="0.875rem",
    )


def flash_error(message: rx.Var | str) -> rx.Component:
    """Error notification box (red tint)."""
    return rx.box(
        rx.hstack(rx.text("✗", color="var(--color-error-border)"), rx.text(message),
                  gap="0.5rem", align="center"),
        background="var(--color-error-bg)",
        border="1px solid var(--color-error-border)",
        border_radius="4px",
        padding="0.75rem 1rem",
        margin_bottom="1rem",
        font_size="0.875rem",
    )


def flash_warning(message: rx.Var | str) -> rx.Component:
    """Warning notification box (amber tint)."""
    return rx.box(
        rx.hstack(rx.text("⚠", color="var(--color-warning-border)"), rx.text(message),
                  gap="0.5rem", align="center"),
        background="var(--color-warning-bg)",
        border="1px solid var(--color-warning-border)",
        border_radius="4px",
        padding="0.75rem 1rem",
        margin_bottom="1rem",
        font_size="0.875rem",
    )


def flash_info(message: rx.Var | str) -> rx.Component:
    """Info notification box (indigo tint)."""
    return rx.box(
        rx.hstack(rx.text("ℹ", color="var(--color-info-border)"), rx.text(message),
                  gap="0.5rem", align="center"),
        background="var(--color-info-bg)",
        border="1px solid var(--color-info-border)",
        border_radius="4px",
        padding="0.75rem 1rem",
        margin_bottom="1rem",
        font_size="0.875rem",
    )


def typed_flash(flash: rx.Var, flash_type: rx.Var) -> rx.Component:
    """Render a flash notification with color based on flash_type.

    flash_type: "success" | "error" | "warning" | "info" (default info).
    Used on change-password, reset-password, and other auth pages.
    """
    return rx.cond(
        flash != "",
        rx.cond(
            flash_type == "success",
            flash_success(flash),
            rx.cond(
                flash_type == "error",
                flash_error(flash),
                rx.cond(
                    flash_type == "warning",
                    flash_warning(flash),
                    flash_info(flash),
                ),
            ),
        ),
        rx.fragment(),
    )


def config_toast(flash: rx.Var, flash_type: rx.Var, dismiss_handler) -> rx.Component:
    """Fixed-position toast notification for config pages.

    Bottom-right corner, white background, 4px colored left border, strong drop
    shadow — reads as a floating overlay, not inline page content.

    Usage:
        config_toast(State.flash, State.flash_type, State.dismiss_flash)
    """
    left_border_color = rx.cond(
        flash_type == "success",
        "var(--color-success-border)",
        rx.cond(
            flash_type == "error",
            "var(--color-error-border)",
            rx.cond(
                flash_type == "warning",
                "var(--color-warning-border)",
                "var(--color-info-border)",
            ),
        ),
    )
    icon = rx.cond(
        flash_type == "success",
        rx.text("✓", color="var(--color-success-border)", font_weight="700", flex_shrink="0"),
        rx.cond(
            flash_type == "error",
            rx.text("✗", color="var(--color-error-border)", font_weight="700", flex_shrink="0"),
            rx.cond(
                flash_type == "warning",
                rx.text("⚠", color="var(--color-warning-border)", font_weight="700", flex_shrink="0"),
                rx.text("ℹ", color="var(--color-info-border)", font_weight="700", flex_shrink="0"),
            ),
        ),
    )
    return rx.cond(
        flash != "",
        rx.box(
            rx.hstack(
                icon,
                rx.text(flash, flex="1", font_size="0.875rem", color="var(--color-body)"),
                rx.button(
                    "✕",
                    on_click=dismiss_handler,
                    background="transparent",
                    border="none",
                    cursor="pointer",
                    font_size="1rem",
                    color="var(--color-muted)",
                    padding="0 0 0 0.5rem",
                    flex_shrink="0",
                    line_height="1",
                ),
                align="center",
                gap="0.6rem",
                width="100%",
            ),
            background="white",
            padding="0.875rem 1rem",
            font_family="var(--font-sans)",
            position="fixed",
            bottom="1.5rem",
            right="1.5rem",
            z_index="9999",
            min_width="16rem",
            max_width="22rem",
            border_radius="0.5rem",
            box_shadow="0 8px 24px rgba(0,0,0,0.18), 0 2px 6px rgba(0,0,0,0.08)",
            border_top="1px solid var(--color-rule)",
            border_right="1px solid var(--color-rule)",
            border_bottom="1px solid var(--color-rule)",
            border_left_width="4px",
            border_left_style="solid",
            border_left_color=left_border_color,
        ),
        rx.fragment(),
    )


def form_modal(
    content: rx.Component,
    is_open: rx.Var,
    max_width: str = "520px",
) -> rx.Component:
    """Full-viewport modal overlay for create/edit/detail forms on config pages.

    Uses the same fixed-position backdrop pattern as confirmation_dialog so the
    modal is always centered in the viewport regardless of scroll position.
    z_index 1050 — above toast (1100) … actually below toast so toast remains
    visible during a save.  Set to 1000 to match confirmation_dialog.

    Usage:
        form_modal(content=rx.vstack(...), is_open=State.show_form)
    """
    return rx.cond(
        is_open,
        rx.box(
            # Backdrop dims the page
            rx.box(
                # Centered card
                rx.box(
                    content,
                    background="white",
                    border_radius="8px",
                    padding="1.5rem",
                    width=f"min({max_width}, 92vw)",
                    max_height="88vh",
                    overflow_y="auto",
                    box_shadow="0 8px 32px rgba(0,0,0,0.20)",
                ),
                display="flex",
                align_items="center",
                justify_content="center",
                position="fixed",
                top="0",
                left="0",
                width="100vw",
                height="100vh",
                z_index="1000",
            ),
            position="fixed",
            top="0",
            left="0",
            width="100vw",
            height="100vh",
            background="rgba(0,0,0,0.45)",
            z_index="999",
        ),
        rx.fragment(),
    )


def role_multi_select(
    options: rx.Var,
    selected_codes: rx.Var,
    toggle_handler,
) -> rx.Component:
    """Scrollable checkbox list for selecting multiple role/designation codes."""
    return rx.box(
        rx.foreach(
            options,
            lambda o: rx.hstack(
                rx.checkbox(
                    checked=selected_codes.contains(o["code"]),
                    on_change=toggle_handler(o["code"]),
                ),
                rx.text(o["label"], font_size="0.875rem"),
                spacing="2",
                align="center",
            ),
        ),
        max_height="200px",
        overflow_y="auto",
        border="1px solid var(--color-rule)",
        border_radius="var(--radius-2)",
        padding="0.5rem",
    )


def _stage_item(
    code: rx.Var,
    idx: rx.Var,
    move_up_handler,
    move_down_handler,
    total: rx.Var,
) -> rx.Component:
    stage_num = idx + 1
    return rx.hstack(
        rx.text(
            stage_num.to(str) + ".",
            font_size="0.8rem",
            font_weight="600",
            color="var(--color-primary)",
            min_width="1.5rem",
        ),
        rx.text(code, font_size="0.85rem"),
        rx.spacer(),
        rx.icon_button(
            rx.icon("chevron-up", size=12),
            aria_label="Move up",
            on_click=move_up_handler(code),
            variant="ghost",
            size="1",
            cursor="pointer",
            disabled=idx == 0,
            type="button",
        ),
        rx.icon_button(
            rx.icon("chevron-down", size=12),
            aria_label="Move down",
            on_click=move_down_handler(code),
            variant="ghost",
            size="1",
            cursor="pointer",
            disabled=idx == total - 1,
            type="button",
        ),
        align="center",
        gap="0.25rem",
        width="100%",
        padding="0.15rem 0",
    )


def role_multi_select_ordered(
    options: rx.Var,
    selected_codes: rx.Var,
    toggle_handler,
    *,
    move_up_handler=None,
    move_down_handler=None,
) -> rx.Component:
    """Scrollable checkbox list for ordered selection with reorder controls."""
    stage_list = rx.fragment()
    if move_up_handler and move_down_handler:
        stage_list = rx.cond(
            selected_codes.length() > 0,  # type: ignore[attr-defined]
            rx.vstack(
                rx.text(
                    "Stage order (use arrows to reorder):",
                    font_size="0.75rem",
                    color="var(--color-muted)",
                    font_weight="600",
                ),
                rx.foreach(
                    selected_codes,
                    lambda code, idx: _stage_item(
                        code, idx, move_up_handler, move_down_handler,
                        selected_codes.length(),  # type: ignore[attr-defined]
                    ),
                ),
                align="start",
                gap="0.15rem",
                width="100%",
                margin_top="0.5rem",
                padding="0.5rem",
                border="1px solid var(--color-rule)",
                border_radius="var(--radius-2)",
                background="var(--color-background, #f5f0eb)",
            ),
            rx.fragment(),
        )

    return rx.box(
        rx.text(
            "Click to add/remove. Stage 1 approves first; last stage is terminal.",
            font_size="0.75rem",
            color="var(--color-muted)",
            margin_bottom="0.25rem",
            font_style="italic",
        ),
        rx.box(
            rx.foreach(
                options,
                lambda o: rx.hstack(
                    rx.checkbox(
                        checked=selected_codes.contains(o["code"]),
                        on_change=toggle_handler(o["code"]),
                    ),
                    rx.text(o["label"], font_size="0.875rem"),
                    spacing="2",
                    align="center",
                ),
            ),
            max_height="200px",
            overflow_y="auto",
            border="1px solid var(--color-rule)",
            border_radius="var(--radius-2)",
            padding="0.5rem",
        ),
        stage_list,
    )


def admin_page(content: rx.Component) -> rx.Component:
    """Wrap admin page content so it is invisible until auth check completes.

    Issue 1 fix: on_load fires AFTER first render. Without this wrapper the
    admin chrome flashes briefly for unauthenticated users before the redirect
    fires. Wrapping in rx.cond(current_user_id != "", ...) shows nothing until
    the guard sets current_user_id, eliminating the flash.

    Use as: return admin_page(rx.vstack(nav_shell(), rx.box(...), page_footer()))
    """
    # Gate on admin_authorized (set in _admin_guard() only after BOTH auth and
    # can("read","user") pass). current_user_id alone is insufficient: an
    # authenticated-but-unauthorized user (e.g. student_001) also has it set.
    return rx.cond(
        BaseState.admin_authorized,
        content,
        rx.fragment(),
    )
