"""Working Days config page — /admin/config/working-days."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    app_shell,
    config_toast,
    primary_btn,
)
from durgam.states.config_timings import WorkingDaysConfigState

_DAY_LABELS_5 = "Monday · Tuesday · Wednesday · Thursday · Friday"
_DAY_LABELS_6 = "Monday · Tuesday · Wednesday · Thursday · Friday · Saturday"


def admin_config_working_days() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
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
                                    ["5", "6"],
                                    name="days_per_week",
                                    value=WorkingDaysConfigState.days_per_week,
                                    on_change=WorkingDaysConfigState.set_days_per_week,
                                    direction="column",
                                    gap="2",
                                ),
                                rx.cond(
                                    WorkingDaysConfigState.days_per_week == "5",
                                    rx.text(
                                        "Working days: " + _DAY_LABELS_5,
                                        font_size="0.85rem",
                                        color="var(--color-muted)",
                                        font_family="var(--font-sans)",
                                    ),
                                    rx.text(
                                        "Working days: " + _DAY_LABELS_6,
                                        font_size="0.85rem",
                                        color="var(--color-muted)",
                                        font_family="var(--font-sans)",
                                    ),
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
                align="start",
                width="100%",
            ),
            container="sm",
        )
    )
