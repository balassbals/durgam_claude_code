"""Working Days config page — /admin/config/working-days."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    nav_shell,
    page_footer,
    primary_btn,
)
from durgam.states.config_timings import WorkingDaysConfigState

_DAY_LABELS_5 = "Monday · Tuesday · Wednesday · Thursday · Friday"
_DAY_LABELS_6 = "Monday · Tuesday · Wednesday · Thursday · Friday · Saturday"


def admin_config_working_days() -> rx.Component:
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
                    "Working Days",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="0.5rem",
                ),
                rx.text(
                    "Configure the institute-wide working week. Affects timetable generation and attendance.",
                    font_size="0.875rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    WorkingDaysConfigState.flash,
                    WorkingDaysConfigState.flash_type,
                    WorkingDaysConfigState.dismiss_flash,
                ),
                rx.cond(
                    WorkingDaysConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    rx.box(
                        rx.form(
                            rx.vstack(
                                rx.text(
                                    "Days per week",
                                    font_size="0.85rem",
                                    color="var(--color-muted)",
                                    font_family="var(--font-sans)",
                                ),
                                rx.radio_group(
                                    rx.flex(
                                        rx.radio("5"),
                                        rx.text(
                                            "5 days — " + _DAY_LABELS_5,
                                            font_size="0.9rem",
                                            font_family="var(--font-sans)",
                                        ),
                                        gap="0.5rem",
                                        align="center",
                                    ),
                                    rx.flex(
                                        rx.radio("6"),
                                        rx.text(
                                            "6 days — " + _DAY_LABELS_6,
                                            font_size="0.9rem",
                                            font_family="var(--font-sans)",
                                        ),
                                        gap="0.5rem",
                                        align="center",
                                    ),
                                    name="days_per_week",
                                    value=WorkingDaysConfigState.days_per_week,
                                    on_change=WorkingDaysConfigState.set_days_per_week,
                                    orientation="vertical",
                                    gap="0.75rem",
                                ),
                                rx.divider(margin_y="0.5rem"),
                                primary_btn("Save", type="submit"),
                                gap="1rem",
                                align="start",
                            ),
                            on_submit=WorkingDaysConfigState.save_working_days,
                            reset_on_submit=False,
                        ),
                        background="white",
                        border="1px solid var(--color-rule)",
                        border_radius="8px",
                        padding="1.75rem",
                        max_width="480px",
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
