"""Vision & Mission management page — /admin/config/vision-mission."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.states.config_vision_mission import VisionMissionConfigState


def _vision_section() -> rx.Component:
    """University vision display + edit form (only shown when can_edit_university)."""
    return rx.vstack(
        rx.hstack(
            rx.heading("University Vision", size="4", font_family="var(--font-sans)"),
            rx.spacer(),
            primary_btn(
                "Edit Vision",
                on_click=VisionMissionConfigState.open_edit_vision,
                font_size="0.85rem",
            ),
            align="center",
            width="100%",
        ),
        rx.box(
            rx.text(
                VisionMissionConfigState.university_vision,
                font_family="var(--font-sans)",
                color="var(--color-body)",
                font_size="0.95rem",
                line_height="1.6",
            ),
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="6px",
            padding="1rem 1.25rem",
            width="100%",
        ),
        align="start",
        gap="0.75rem",
        width="100%",
    )


def _vision_edit_modal() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading("Edit University Vision", size="4", font_family="var(--font-sans)"),
            rx.form(
                rx.vstack(
                    rx.text("Vision statement", font_size="0.85rem", color="var(--color-muted)"),
                    rx.text_area(
                        name="form_vision",
                        value=VisionMissionConfigState.form_vision,
                        on_change=VisionMissionConfigState.set_form_vision,
                        placeholder="Enter the university vision statement…",
                        rows="4",
                        width="100%",
                        font_family="var(--font-sans)",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=VisionMissionConfigState.cancel_vision_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="0.75rem",
                    align="start",
                    width="100%",
                ),
                on_submit=VisionMissionConfigState.save_university_vision,
                reset_on_submit=False,
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        is_open=VisionMissionConfigState.show_vision_form,
    )


def _mission_row(m: dict) -> rx.Component:
    return rx.hstack(
        rx.text(
            m["statement"],
            flex="1",
            font_family="var(--font-sans)",
            font_size="0.9rem",
            color="var(--color-body)",
        ),
        rx.hstack(
            rx.button(
                "↑",
                on_click=VisionMissionConfigState.move_mission_up(  # type: ignore[call-arg]
                    m["id"]
                ),
                background="transparent",
                border="1px solid var(--color-rule)",
                cursor="pointer",
                padding="0.2rem 0.5rem",
                font_size="0.85rem",
                border_radius="4px",
                title="Move up",
            ),
            rx.button(
                "↓",
                on_click=VisionMissionConfigState.move_mission_down(  # type: ignore[call-arg]
                    m["id"]
                ),
                background="transparent",
                border="1px solid var(--color-rule)",
                cursor="pointer",
                padding="0.2rem 0.5rem",
                font_size="0.85rem",
                border_radius="4px",
                title="Move down",
            ),
            rx.button(
                "Edit",
                on_click=VisionMissionConfigState.open_edit_mission(  # type: ignore[call-arg]
                    m["id"], m["statement"]
                ),
                background="transparent",
                border="1px solid var(--color-primary)",
                color="var(--color-primary)",
                cursor="pointer",
                padding="0.2rem 0.6rem",
                font_size="0.8rem",
                border_radius="4px",
            ),
            rx.button(
                "Remove",
                on_click=VisionMissionConfigState.remove_mission(  # type: ignore[call-arg]
                    m["id"]
                ),
                background="transparent",
                border="1px solid var(--color-destructive)",
                color="var(--color-destructive)",
                cursor="pointer",
                padding="0.2rem 0.6rem",
                font_size="0.8rem",
                border_radius="4px",
            ),
            gap="0.4rem",
            flex_shrink="0",
        ),
        align="start",
        gap="0.75rem",
        width="100%",
        padding="0.6rem 0.75rem",
        border_bottom="1px solid var(--color-rule)",
        background="white",
    )


def _missions_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("Mission Statements", size="4", font_family="var(--font-sans)"),
            rx.spacer(),
            primary_btn(
                "+ Add Mission",
                on_click=VisionMissionConfigState.open_add_mission,
                font_size="0.85rem",
            ),
            align="center",
            width="100%",
        ),
        rx.cond(
            VisionMissionConfigState.university_missions.length() == 0,  # type: ignore[attr-defined]
            rx.box(
                rx.text(
                    "No mission statements added yet. Click '+ Add Mission' to add one.",
                    color="var(--color-muted)",
                    font_size="0.9rem",
                    font_family="var(--font-sans)",
                ),
                padding="1rem",
                border="1px dashed var(--color-rule)",
                border_radius="6px",
                background="white",
                width="100%",
            ),
            rx.box(
                rx.foreach(VisionMissionConfigState.university_missions, _mission_row),
                border="1px solid var(--color-rule)",
                border_radius="6px",
                overflow="hidden",
                width="100%",
            ),
        ),
        align="start",
        gap="0.75rem",
        width="100%",
    )


def _mission_edit_modal() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    VisionMissionConfigState.editing_mission_id == "",
                    "Add Mission Statement",
                    "Edit Mission Statement",
                ),
                size="4",
                font_family="var(--font-sans)",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_mission_id",
                        value=VisionMissionConfigState.editing_mission_id,
                    ),
                    rx.text("Mission statement", font_size="0.85rem", color="var(--color-muted)"),
                    rx.text_area(
                        name="form_mission",
                        value=VisionMissionConfigState.form_mission,
                        on_change=VisionMissionConfigState.set_form_mission,
                        placeholder="Enter mission statement…",
                        rows="3",
                        width="100%",
                        font_family="var(--font-sans)",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=VisionMissionConfigState.cancel_mission_modal,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="0.75rem",
                    align="start",
                    width="100%",
                ),
                on_submit=VisionMissionConfigState.save_mission,
                reset_on_submit=False,
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        is_open=VisionMissionConfigState.show_mission_modal,
    )


def _dept_row(row: dict) -> rx.Component:
    return rx.hstack(
        rx.vstack(
            rx.text(
                row["name"],
                font_weight="600",
                font_size="0.9rem",
                font_family="var(--font-sans)",
            ),
            rx.text(
                row["code"],
                color="var(--color-muted)",
                font_size="0.8rem",
                font_family="var(--font-sans)",
            ),
            align="start",
            gap="0.1rem",
            flex="1",
        ),
        rx.hstack(
            rx.text(
                rx.cond(row["has_vision"] == "Yes", "Configured", "Not configured"),
                font_size="0.8rem",
                color=rx.cond(row["has_vision"] == "Yes", "var(--color-success-border)", "var(--color-muted)"),
                font_family="var(--font-sans)",
            ),
            rx.link(
                "Edit V&M",
                href="/admin/config/vision-mission/departments/" + row["code"],
                font_size="0.85rem",
                color="var(--color-primary)",
                font_family="var(--font-sans)",
                padding="0.3rem 0.75rem",
                border="1px solid var(--color-primary)",
                border_radius="4px",
                text_decoration="none",
            ),
            gap="1rem",
            align="center",
        ),
        align="center",
        justify="between",
        width="100%",
        padding="0.75rem 1rem",
        border_bottom="1px solid var(--color-rule)",
        background="white",
    )


def _departments_section() -> rx.Component:
    return rx.vstack(
        rx.heading(
            "Department Vision & Mission",
            size="4",
            font_family="var(--font-sans)",
        ),
        rx.text(
            "Each department can configure its own vision and mission. Click 'Edit V&M' to manage.",
            font_size="0.85rem",
            color="var(--color-muted)",
            font_family="var(--font-sans)",
        ),
        rx.box(
            rx.foreach(VisionMissionConfigState.dept_rows, _dept_row),
            border="1px solid var(--color-rule)",
            border_radius="6px",
            overflow="hidden",
            width="100%",
        ),
        align="start",
        gap="0.75rem",
        width="100%",
    )


def admin_config_vision_mission() -> rx.Component:
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
                    "Vision & Mission",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    VisionMissionConfigState.flash,
                    VisionMissionConfigState.flash_type,
                    VisionMissionConfigState.dismiss_flash,
                ),
                _vision_edit_modal(),
                _mission_edit_modal(),
                rx.cond(
                    VisionMissionConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    rx.vstack(
                        # University section — only visible to Registrar family
                        rx.cond(
                            VisionMissionConfigState.can_edit_university,
                            rx.vstack(
                                _vision_section(),
                                rx.divider(margin_y="1.5rem"),
                                _missions_section(),
                                rx.divider(margin_y="1.5rem"),
                                align="start",
                                gap="0",
                                width="100%",
                            ),
                            rx.fragment(),
                        ),
                        _departments_section(),
                        align="start",
                        gap="0",
                        width="100%",
                    ),
                ),
                padding="2rem",
                max_width="1000px",
                width="100%",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
