"""Department management page — /admin/config/departments."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
    typed_flash,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_department import AdminDepartmentsState


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
                "View Details",
                on_click=AdminDepartmentsState.open_detail(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["name"]
                ),
            ),
            rx.menu.item(
                "Edit",
                on_click=AdminDepartmentsState.open_edit(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["code"], row["name"],
                    row["school_id"], row["main_campus_id"],
                ),
            ),
            rx.menu.item(
                "Deactivate",
                on_click=AdminDepartmentsState.open_soft_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                    row["id"], row["name"]
                ),
                color="var(--color-danger, #c0392b)",
            ),
        ),
    )


def _inline_form() -> rx.Component:
    return rx.cond(
        AdminDepartmentsState.show_form,
        rx.box(
            rx.heading(
                rx.cond(
                    AdminDepartmentsState.editing_id == "",
                    "New Department",
                    "Edit Department",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            # rx.form collects all named inputs and sends them as form_data dict
            # to save_department. This guarantees the handler receives current values
            # even if on_change round-trips were dropped (M3 pattern).
            rx.form(
                rx.vstack(
                    # Hidden field carries editing_id so save_department knows
                    # whether this is a create or edit operation.
                    rx.input(
                        type="hidden",
                        name="editing_id",
                        value=AdminDepartmentsState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Code", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_code",
                            value=AdminDepartmentsState.form_code,
                            on_change=AdminDepartmentsState.set_form_code,
                            placeholder="e.g. DMACS",
                            disabled=AdminDepartmentsState.editing_id != "",
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
                            value=AdminDepartmentsState.form_name,
                            on_change=AdminDepartmentsState.set_form_name,
                            placeholder="Full department name",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("School", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select(
                            rx.foreach(
                                AdminDepartmentsState.schools_dropdown,
                                lambda s: rx.select.item(
                                    s["code"] + " — " + s["name"],
                                    value=s["id"],
                                ),
                            ),
                            value=AdminDepartmentsState.form_school_id,
                            on_change=AdminDepartmentsState.set_form_school_id,
                            placeholder="Select school",
                            name="form_school_id",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Main Campus",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.select(
                            rx.foreach(
                                AdminDepartmentsState.campuses_dropdown,
                                lambda c: rx.select.item(
                                    c["code"] + " — " + c["name"],
                                    value=c["id"],
                                ),
                            ),
                            value=AdminDepartmentsState.form_main_campus_id,
                            on_change=AdminDepartmentsState.set_form_main_campus_id,
                            placeholder="Select main campus",
                            name="form_main_campus_id",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn("Cancel", on_click=AdminDepartmentsState.cancel_form),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=AdminDepartmentsState.save_department,
                reset_on_submit=False,
            ),
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="8px",
            padding="1.5rem",
            margin_bottom="1.5rem",
            width="100%",
            max_width="560px",
        ),
        rx.fragment(),
    )


def _campus_chip(link: dict) -> rx.Component:
    """A tag-style chip for a linked campus with a Remove button."""
    return rx.hstack(
        rx.text(
            link["campus_code"],
            font_size="0.85rem",
            font_family="var(--font-sans)",
            font_weight="500",
        ),
        rx.button(
            "Remove",
            on_click=AdminDepartmentsState.open_remove_campus_confirm(  # type: ignore[call-arg, func-returns-value]
                link["campus_id"]
            ),
            font_size="0.75rem",
            background="transparent",
            border="none",
            color="var(--color-danger, #c0392b)",
            cursor="pointer",
            padding="0",
        ),
        background="var(--color-background, #f5f0eb)",
        border="1px solid var(--color-rule)",
        border_radius="4px",
        padding="0.25rem 0.5rem",
        align="center",
        gap="0.4rem",
    )


def _subdept_row(sd: dict) -> rx.Component:
    return rx.hstack(
        rx.text(
            sd["code"],
            font_size="0.85rem",
            font_weight="600",
            font_family="var(--font-sans)",
            color="var(--color-primary)",
            min_width="6rem",
        ),
        rx.text(
            sd["name"],
            font_size="0.85rem",
            font_family="var(--font-sans)",
            color="var(--color-body)",
        ),
        gap="0.75rem",
        padding_y="0.3rem",
    )


def _detail_panel() -> rx.Component:
    """Inline detail panel showing campus links and sub-departments."""
    return rx.box(
        rx.hstack(
            rx.heading(
                AdminDepartmentsState.detail_dept_name,
                size="4",
                font_family="var(--font-sans)",
            ),
            rx.spacer(),
            rx.button(
                "Close",
                on_click=AdminDepartmentsState.close_detail,
                background="transparent",
                border="1px solid var(--color-rule)",
                color="var(--color-body)",
                padding="0.25rem 0.75rem",
                border_radius="4px",
                cursor="pointer",
                font_family="var(--font-sans)",
                font_size="0.85rem",
            ),
            align="center",
            width="100%",
            margin_bottom="1.25rem",
        ),
        # ── Campuses section ──────────────────────────────────────────────────
        rx.text(
            "Campuses",
            font_weight="600",
            font_size="0.9rem",
            font_family="var(--font-sans)",
            color="var(--color-muted)",
            margin_bottom="0.5rem",
        ),
        rx.cond(
            AdminDepartmentsState.detail_campus_links.length() == 0,  # type: ignore[attr-defined]
            rx.text(
                "No campuses linked.",
                font_size="0.85rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.hstack(
                rx.foreach(
                    AdminDepartmentsState.detail_campus_links,
                    _campus_chip,
                ),
                flex_wrap="wrap",
                gap="0.5rem",
            ),
        ),
        # Add campus row
        rx.hstack(
            rx.select(
                rx.foreach(
                    AdminDepartmentsState.available_campuses,
                    lambda c: rx.select.item(c["code"], value=c["id"]),
                ),
                value=AdminDepartmentsState.add_campus_id,
                on_change=AdminDepartmentsState.set_add_campus_id,
                placeholder="Add campus…",
                width="12rem",
            ),
            primary_btn(
                "Add",
                on_click=AdminDepartmentsState.add_campus_link,
            ),
            align="center",
            gap="0.5rem",
            margin_top="0.75rem",
            margin_bottom="1.25rem",
        ),
        rx.divider(margin_y="0.75rem"),
        # ── Sub-departments section ───────────────────────────────────────────
        rx.text(
            "Sub-Departments",
            font_weight="600",
            font_size="0.9rem",
            font_family="var(--font-sans)",
            color="var(--color-muted)",
            margin_bottom="0.5rem",
        ),
        rx.cond(
            AdminDepartmentsState.detail_sub_depts.length() == 0,  # type: ignore[attr-defined]
            rx.text(
                "No sub-departments.",
                font_size="0.85rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.vstack(
                rx.foreach(AdminDepartmentsState.detail_sub_depts, _subdept_row),
                align="start",
                gap="0",
            ),
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1.5rem",
        margin_bottom="1.5rem",
        width="100%",
        max_width="600px",
    )


def admin_config_departments() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Departments",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        "+ New Department",
                        on_click=AdminDepartmentsState.open_create,
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1.5rem",
                ),
                typed_flash(
                    AdminDepartmentsState.flash,
                    AdminDepartmentsState.flash_type,
                ),
                _inline_form(),
                rx.cond(
                    AdminDepartmentsState.show_detail,
                    _detail_panel(),
                    rx.fragment(),
                ),
                rx.cond(
                    AdminDepartmentsState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AdminDepartmentsState.departments,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(
                                key="school_code",
                                label="School",
                                hidden_on_card=False,
                            ),
                            TableColumn(
                                key="campus_count",
                                label="Campuses",
                                hidden_on_card=True,
                            ),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No departments found.",
                    ),
                ),
                # Soft-delete confirmation dialog
                confirmation_dialog(
                    is_open=AdminDepartmentsState.confirm_open,
                    title=AdminDepartmentsState.confirm_title,
                    body=AdminDepartmentsState.confirm_body,
                    on_confirm=AdminDepartmentsState.soft_delete_department,
                    on_cancel=AdminDepartmentsState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                # Remove-campus confirmation dialog
                confirmation_dialog(
                    is_open=AdminDepartmentsState.confirm_remove_campus_open,
                    title="Remove campus link?",
                    body="This will unlink the campus from this department. Existing data is preserved.",
                    on_confirm=AdminDepartmentsState.remove_campus_link,
                    on_cancel=AdminDepartmentsState.cancel_remove_campus,
                    confirm_label="Remove",
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
