"""Course management page — /admin/config/courses."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
    config_toast,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_course import AdminCoursesState


def _kebab(row: dict) -> rx.Component:
    return rx.menu.root(
        rx.menu.trigger(
            rx.button(
                "⋮",
                background="transparent",
                border="none",
                cursor="pointer",
                font_size="1.2rem",
                color="var(--color-muted)",
                padding="0.1rem 0.4rem",
            )
        ),
        rx.menu.content(
            rx.menu.item(
                "Edit",
                on_click=AdminCoursesState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"],
                    row["code"],
                    row["name"],
                    row["program_id"],
                    row["department_id"],
                    row["credits"],
                    row["lecture"],
                    row["tutorial"],
                    row["practical"],
                    row["evaluation"],
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=AdminCoursesState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["name"]
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


def _inline_form() -> rx.Component:
    return rx.cond(
        AdminCoursesState.show_form,
        rx.box(
            rx.heading(
                rx.cond(AdminCoursesState.editing_id == "", "New Course", "Edit Course"),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            # rx.form collects all named inputs and sends them as form_data dict
            # to save_course. This guarantees the handler receives current values
            # even if on_change round-trips were dropped (M3 pattern).
            rx.form(
                rx.vstack(
                    # Hidden field carries editing_id so save_course knows
                    # whether this is a create or edit operation.
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=AdminCoursesState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Code", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=AdminCoursesState.form_code,
                            on_change=AdminCoursesState.set_form_code,
                            placeholder="e.g. MAT101",
                            disabled=AdminCoursesState.editing_id != "",
                            max_length=20,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Name", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=AdminCoursesState.form_name,
                            on_change=AdminCoursesState.set_form_name,
                            placeholder="Course name",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Program", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select program"),
                            rx.select.content(
                                rx.foreach(
                                    AdminCoursesState.programs_dropdown,
                                    lambda p: rx.select.item(p["label"], value=p["id"]),
                                ),
                            ),
                            value=AdminCoursesState.form_program_id,
                            on_change=AdminCoursesState.set_form_program_id,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Department", font_size="0.85rem", color="var(--color-muted)"
                        ),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select department"),
                            rx.select.content(
                                rx.foreach(
                                    AdminCoursesState.departments_dropdown,
                                    lambda d: rx.select.item(d["label"], value=d["id"]),
                                ),
                            ),
                            value=AdminCoursesState.form_department_id,
                            on_change=AdminCoursesState.set_form_department_id,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text(
                                "Credits", font_size="0.85rem", color="var(--color-muted)"
                            ),
                            rx.input(
                                name="form_credits",
                                value=AdminCoursesState.form_credits,
                                on_change=AdminCoursesState.set_form_credits,
                                placeholder="0",
                                type="number",
                                min="0",
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                "Lecture", font_size="0.85rem", color="var(--color-muted)"
                            ),
                            rx.input(
                                name="form_lecture",
                                value=AdminCoursesState.form_lecture,
                                on_change=AdminCoursesState.set_form_lecture,
                                placeholder="0",
                                type="number",
                                min="0",
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                "Tutorial", font_size="0.85rem", color="var(--color-muted)"
                            ),
                            rx.input(
                                name="form_tutorial",
                                value=AdminCoursesState.form_tutorial,
                                on_change=AdminCoursesState.set_form_tutorial,
                                placeholder="0",
                                type="number",
                                min="0",
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text(
                                "Practical",
                                font_size="0.85rem",
                                color="var(--color-muted)",
                            ),
                            rx.input(
                                name="form_practical",
                                value=AdminCoursesState.form_practical,
                                on_change=AdminCoursesState.set_form_practical,
                                placeholder="0",
                                type="number",
                                min="0",
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                        gap="0.75rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Evaluation", font_size="0.85rem", color="var(--color-muted)"
                        ),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select evaluation"),
                            rx.select.content(
                                rx.select.item("I — Internal only", value="I"),
                                rx.select.item("E — External only", value="E"),
                                rx.select.item("IE — Internal + External", value="IE"),
                            ),
                            value=AdminCoursesState.form_evaluation,
                            on_change=AdminCoursesState.set_form_evaluation,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn("Cancel", on_click=AdminCoursesState.cancel_form, type="button"),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=AdminCoursesState.save_course,
                reset_on_submit=False,
            ),
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="8px",
            padding="1.5rem",
            margin_bottom="1.5rem",
            width="100%",
            max_width="600px",
        ),
        rx.fragment(),
    )


def admin_config_courses() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Courses",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn("+ New Course", on_click=AdminCoursesState.open_create),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                config_toast(AdminCoursesState.flash, AdminCoursesState.flash_type, AdminCoursesState.dismiss_flash),
                _inline_form(),
                rx.cond(
                    AdminCoursesState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AdminCoursesState.courses,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(
                                key="department_code",
                                label="Department",
                                hidden_on_card=False,
                            ),
                            TableColumn(
                                key="credits",
                                label="Credits",
                                hidden_on_card=True,
                            ),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No courses found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=AdminCoursesState.confirm_open,
                    title=AdminCoursesState.confirm_title,
                    body=AdminCoursesState.confirm_body,
                    on_confirm=AdminCoursesState.soft_delete_course,
                    on_cancel=AdminCoursesState.cancel_confirm,
                    confirm_label="Deactivate",
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
