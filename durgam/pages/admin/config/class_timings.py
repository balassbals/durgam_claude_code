"""Class Timings config page — /admin/config/class-timings."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    nav_shell,
    page_footer,
    primary_btn,
)
from durgam.states.config_timings import ClassTimingsConfigState


def _field(label: str, child: rx.Component, hint: str = "") -> rx.Component:
    return rx.vstack(
        rx.text(label, font_size="0.85rem", color="var(--color-muted)", font_family="var(--font-sans)"),
        child,
        rx.cond(
            hint != "",
            rx.text(hint, font_size="0.75rem", color="var(--color-muted)", font_family="var(--font-sans)"),
            rx.fragment(),
        ),
        align="start",
        gap="0.25rem",
        width="100%",
    )


def admin_config_class_timings() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.link(
                    "← Configuration",
                    href="/admin/config",
                    font_size="0.85rem",
                    color="var(--color-primary)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                    display="block",
                ),
                rx.heading(
                    "Class Timings",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="0.5rem",
                ),
                rx.text(
                    "Institute-wide class period configuration. Changes apply to all timetables.",
                    font_size="0.875rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    ClassTimingsConfigState.flash,
                    ClassTimingsConfigState.flash_type,
                    ClassTimingsConfigState.dismiss_flash,
                ),
                rx.cond(
                    ClassTimingsConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    rx.box(
                        rx.form(
                            rx.vstack(
                                _field(
                                    "Periods per day",
                                    rx.input(
                                        name="periods_per_day",
                                        type="number",
                                        value=ClassTimingsConfigState.periods_per_day,
                                        on_change=ClassTimingsConfigState.set_periods_per_day,
                                        min="1",
                                        max="20",
                                        width="160px",
                                        font_family="var(--font-sans)",
                                    ),
                                    "Typical range: 6–10",
                                ),
                                _field(
                                    "Period duration (minutes)",
                                    rx.input(
                                        name="period_duration_minutes",
                                        type="number",
                                        value=ClassTimingsConfigState.period_duration_minutes,
                                        on_change=ClassTimingsConfigState.set_period_duration_minutes,
                                        min="10",
                                        max="180",
                                        width="160px",
                                        font_family="var(--font-sans)",
                                    ),
                                    "Typical range: 45–60 minutes",
                                ),
                                _field(
                                    "First period start time (HH:MM, 24-hour)",
                                    rx.input(
                                        name="first_period_start",
                                        type="text",
                                        value=ClassTimingsConfigState.first_period_start,
                                        on_change=ClassTimingsConfigState.set_first_period_start,
                                        placeholder="08:00",
                                        max_length=5,
                                        width="160px",
                                        font_family="var(--font-sans)",
                                    ),
                                    "e.g. 08:00 for 8 AM",
                                ),
                                rx.divider(margin_y="0.5rem"),
                                rx.text(
                                    "Break configuration (optional)",
                                    font_weight="600",
                                    font_size="0.9rem",
                                    font_family="var(--font-sans)",
                                ),
                                _field(
                                    "Break after period (leave blank for no break)",
                                    rx.input(
                                        name="break_after_period",
                                        type="number",
                                        value=ClassTimingsConfigState.break_after_period,
                                        on_change=ClassTimingsConfigState.set_break_after_period,
                                        min="0",
                                        placeholder="e.g. 4",
                                        width="160px",
                                        font_family="var(--font-sans)",
                                    ),
                                    "Period number after which the break occurs",
                                ),
                                _field(
                                    "Break duration (minutes)",
                                    rx.input(
                                        name="break_duration_minutes",
                                        type="number",
                                        value=ClassTimingsConfigState.break_duration_minutes,
                                        on_change=ClassTimingsConfigState.set_break_duration_minutes,
                                        min="0",
                                        placeholder="e.g. 45",
                                        width="160px",
                                        font_family="var(--font-sans)",
                                    ),
                                    "Required if break after period is set",
                                ),
                                rx.divider(margin_y="0.5rem"),
                                primary_btn("Save", type="submit"),
                                gap="1rem",
                                align="start",
                            ),
                            on_submit=ClassTimingsConfigState.save_class_timings,
                            reset_on_submit=False,
                        ),
                        background="white",
                        border="1px solid var(--color-rule)",
                        border_radius="8px",
                        padding="1.75rem",
                        max_width="520px",
                    ),
                ),
                padding="2rem",
                max_width="1200px",
                width="100%",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
