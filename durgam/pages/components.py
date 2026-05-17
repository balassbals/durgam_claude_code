"""Shared page components for authenticated DURGAM pages."""

from __future__ import annotations

import reflex as rx

from durgam.states.auth import AuthState
from durgam.states.base import BaseState


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
