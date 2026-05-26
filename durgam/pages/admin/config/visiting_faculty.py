"""Visiting faculty management page — /admin/config/visiting-faculty."""

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
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_visiting_faculty import VisitingFacultyConfigState


def _approval_cell(row: dict) -> rx.Component:
    return rx.cond(
        VisitingFacultyConfigState.can_approve,
        rx.box(
            rx.cond(
                row["approved"] == "yes",
                rx.badge(
                    "Approved",
                    color_scheme="green",
                    variant="soft",
                    cursor="pointer",
                    on_click=VisitingFacultyConfigState.toggle_approval(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["approved"]
                    ),
                ),
                rx.badge(
                    "Pending",
                    color_scheme="amber",
                    variant="soft",
                    cursor="pointer",
                    on_click=VisitingFacultyConfigState.toggle_approval(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["approved"]
                    ),
                ),
            ),
        ),
        rx.cond(
            row["approved"] == "yes",
            rx.badge("Approved", color_scheme="green", variant="soft"),
            rx.badge("Pending", color_scheme="amber", variant="soft"),
        ),
    )


def _kebab(row: dict) -> rx.Component:
    return rx.hstack(
        _approval_cell(row),
        rx.menu.root(
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
                    on_click=VisitingFacultyConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["name"], row["designation"],
                        row["organization"], row["expertise"],
                        row["available_from"], row["available_to"],
                    ),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=VisitingFacultyConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["name"]
                    ),
                    color="var(--color-danger, #c0392b)",
                ),
            ),
        ),
        align="center",
        gap="0.5rem",
    )


def _dept_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Department:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select department"),
            rx.select.content(
                rx.foreach(
                    VisitingFacultyConfigState.dept_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=VisitingFacultyConfigState.selected_dept_id,
            on_change=VisitingFacultyConfigState.on_dept_change,
            width="320px",
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    VisitingFacultyConfigState.editing_id == "",
                    "New Visiting Faculty",
                    "Edit Visiting Faculty",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=VisitingFacultyConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=VisitingFacultyConfigState.form_name,
                            on_change=VisitingFacultyConfigState.set_form_name,
                            placeholder="Full name",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Designation *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_designation",
                            value=VisitingFacultyConfigState.form_designation,
                            on_change=VisitingFacultyConfigState.set_form_designation,
                            placeholder="e.g. Professor",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Organization *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_organization",
                            value=VisitingFacultyConfigState.form_organization,
                            on_change=VisitingFacultyConfigState.set_form_organization,
                            placeholder="e.g. IISc Bangalore",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Expertise *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_expertise",
                            value=VisitingFacultyConfigState.form_expertise,
                            on_change=VisitingFacultyConfigState.set_form_expertise,
                            placeholder="e.g. Quantum Physics",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Available From *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_available_from",
                            type="date",
                            value=VisitingFacultyConfigState.form_available_from,
                            on_change=VisitingFacultyConfigState.set_form_available_from,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Available To *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_available_to",
                            type="date",
                            value=VisitingFacultyConfigState.form_available_to,
                            on_change=VisitingFacultyConfigState.set_form_available_to,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=VisitingFacultyConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=VisitingFacultyConfigState.save_visitor,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=VisitingFacultyConfigState.show_form,
    )


def admin_config_visiting_faculty() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Visiting Faculty",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        "+ Add",
                        on_click=VisitingFacultyConfigState.open_create,
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.hstack(
                    _dept_selector(),
                    gap="1.5rem",
                    flex_wrap="wrap",
                ),
                rx.box(height="1rem"),
                config_toast(
                    VisitingFacultyConfigState.flash,
                    VisitingFacultyConfigState.flash_type,
                    VisitingFacultyConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    VisitingFacultyConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=VisitingFacultyConfigState.visitors,
                        columns=[
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="designation", label="Designation"),
                            TableColumn(key="organization", label="Organization"),
                            TableColumn(key="expertise", label="Expertise"),
                            TableColumn(key="available_from", label="From"),
                            TableColumn(key="available_to", label="To"),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No visiting faculty records found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=VisitingFacultyConfigState.confirm_open,
                    title=VisitingFacultyConfigState.confirm_title,
                    body=VisitingFacultyConfigState.confirm_body,
                    on_confirm=VisitingFacultyConfigState.soft_delete_visitor,
                    on_cancel=VisitingFacultyConfigState.cancel_confirm,
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
