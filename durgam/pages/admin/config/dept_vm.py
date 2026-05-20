"""Department Vision & Mission editor — /admin/config/vision-mission/departments/[dept_code]."""

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
from durgam.states.config_dept_vm import DeptVMConfigState


def _vision_section() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.heading("Vision", size="4", font_family="var(--font-sans)"),
            rx.spacer(),
            primary_btn(
                "Edit Vision",
                on_click=DeptVMConfigState.open_edit_vision,
                font_size="0.85rem",
                padding="0.35rem 0.9rem",
            ),
            align="center",
            width="100%",
        ),
        rx.box(
            rx.text(
                DeptVMConfigState.dept_vision,
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
            rx.heading("Edit Department Vision", size="4", font_family="var(--font-sans)"),
            rx.form(
                rx.vstack(
                    rx.input(type="hidden", name="dept_id", value=DeptVMConfigState.dept_id),
                    rx.text("Vision statement", font_size="0.85rem", color="var(--color-muted)"),
                    rx.text_area(
                        name="form_vision",
                        value=DeptVMConfigState.form_vision,
                        on_change=DeptVMConfigState.set_form_vision,
                        placeholder="Enter the department vision statement…",
                        rows="4",
                        width="100%",
                        font_family="var(--font-sans)",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=DeptVMConfigState.cancel_vision_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="0.75rem",
                    align="start",
                    width="100%",
                ),
                on_submit=DeptVMConfigState.save_dept_vision,
                reset_on_submit=False,
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        is_open=DeptVMConfigState.show_vision_form,
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
                on_click=DeptVMConfigState.move_mission_up(m["id"]),  # type: ignore[call-arg]
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
                on_click=DeptVMConfigState.move_mission_down(m["id"]),  # type: ignore[call-arg]
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
                on_click=DeptVMConfigState.open_edit_mission(m["id"], m["statement"]),  # type: ignore[call-arg]
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
                on_click=DeptVMConfigState.remove_mission(m["id"]),  # type: ignore[call-arg]
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
                on_click=DeptVMConfigState.open_add_mission,
                font_size="0.85rem",
                padding="0.35rem 0.9rem",
            ),
            align="center",
            width="100%",
        ),
        rx.cond(
            DeptVMConfigState.dept_missions.length() == 0,  # type: ignore[attr-defined]
            rx.box(
                rx.text(
                    "No mission statements yet. Click '+ Add Mission' to add one.",
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
                rx.foreach(DeptVMConfigState.dept_missions, _mission_row),
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
                    DeptVMConfigState.editing_mission_id == "",
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
                        value=DeptVMConfigState.editing_mission_id,
                    ),
                    rx.text("Mission statement", font_size="0.85rem", color="var(--color-muted)"),
                    rx.text_area(
                        name="form_mission",
                        value=DeptVMConfigState.form_mission,
                        on_change=DeptVMConfigState.set_form_mission,
                        placeholder="Enter mission statement…",
                        rows="3",
                        width="100%",
                        font_family="var(--font-sans)",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=DeptVMConfigState.cancel_mission_modal,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="0.75rem",
                    align="start",
                    width="100%",
                ),
                on_submit=DeptVMConfigState.save_mission,
                reset_on_submit=False,
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        is_open=DeptVMConfigState.show_mission_modal,
    )


def admin_config_dept_vm() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.link(
                    "← Vision & Mission",
                    href="/admin/config/vision-mission",
                    font_size="0.85rem",
                    color="var(--color-primary)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                    display="block",
                ),
                rx.heading(
                    DeptVMConfigState.dept_name + " — Vision & Mission",
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="0.5rem",
                ),
                rx.text(
                    "Department code: " + DeptVMConfigState.dept_code,
                    font_size="0.85rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                config_toast(
                    DeptVMConfigState.flash,
                    DeptVMConfigState.flash_type,
                    DeptVMConfigState.dismiss_flash,
                ),
                _vision_edit_modal(),
                _mission_edit_modal(),
                rx.cond(
                    DeptVMConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    rx.vstack(
                        _vision_section(),
                        rx.divider(margin_y="1.5rem"),
                        _missions_section(),
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
