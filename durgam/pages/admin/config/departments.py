"""Department management page — /admin/config/departments."""

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
    return form_modal(
        content=rx.vstack(
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
            rx.form(
                rx.vstack(
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
                        rx.select.root(
                            rx.select.trigger(placeholder="Select school"),
                            rx.select.content(
                                rx.foreach(
                                    AdminDepartmentsState.schools_dropdown,
                                    lambda s: rx.select.item(s["label"], value=s["id"]),
                                ),
                            ),
                            value=AdminDepartmentsState.form_school_id,
                            on_change=AdminDepartmentsState.set_form_school_id,
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
                        rx.select.root(
                            rx.select.trigger(placeholder="Select main campus"),
                            rx.select.content(
                                rx.foreach(
                                    AdminDepartmentsState.campuses_dropdown,
                                    lambda c: rx.select.item(c["label"], value=c["id"]),
                                ),
                            ),
                            value=AdminDepartmentsState.form_main_campus_id,
                            on_change=AdminDepartmentsState.set_form_main_campus_id,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn("Cancel", on_click=AdminDepartmentsState.cancel_form, type="button"),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=AdminDepartmentsState.save_department,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=AdminDepartmentsState.show_form,
    )


def _campus_chip(link: dict) -> rx.Component:
    """A tag-style chip for a linked campus.

    Bug C: shows a 'main' badge when this campus is the department's main campus.
    Bug B: Remove triggers either the promote-and-remove flow (main campus) or
    the standard confirm dialog (non-main campus) — decided in open_remove_campus_confirm.
    """
    is_main = AdminDepartmentsState.detail_main_campus_id == link["campus_id"]
    return rx.hstack(
        rx.text(
            link["campus_code"],
            font_size="0.85rem",
            font_family="var(--font-sans)",
            font_weight="500",
        ),
        rx.cond(
            is_main,
            rx.badge(
                "main",
                color_scheme="indigo",
                variant="soft",
                font_size="0.7rem",
            ),
            rx.fragment(),
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
    """Modal detail panel showing campus links and sub-departments."""
    return form_modal(
        content=rx.vstack(
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
            rx.select.root(
                rx.select.trigger(placeholder="Add campus…"),
                rx.select.content(
                    rx.foreach(
                        AdminDepartmentsState.available_campuses,
                        lambda c: rx.select.item(c["label"], value=c["id"]),
                    ),
                ),
                value=AdminDepartmentsState.add_campus_id,
                on_change=AdminDepartmentsState.set_add_campus_id,
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
        rx.hstack(
            rx.text(
                "Sub-Departments",
                font_weight="600",
                font_size="0.9rem",
                font_family="var(--font-sans)",
                color="var(--color-muted)",
            ),
            rx.text(
                "(read-only at M3 — management deferred to a future milestone)",
                font_size="0.78rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            align="center",
            gap="0.5rem",
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
            align="start",
            gap="0.5rem",
            width="100%",
        ),
        is_open=AdminDepartmentsState.show_detail,
        max_width="700px",
    )


def _promote_remove_modal() -> rx.Component:
    """Modal for removing the main campus — requires selecting a replacement.

    Bug B: selecting a non-main campus for removal goes through the standard
    confirmation_dialog. Selecting the main campus goes through this modal which
    forces the user to choose a replacement before confirming.
    """
    return form_modal(
        content=rx.vstack(
            rx.heading(
                AdminDepartmentsState.confirm_promote_remove_title,
                size="4",
                font_family="var(--font-sans)",
            ),
            rx.text(
                AdminDepartmentsState.confirm_promote_remove_body,
                font_size="0.875rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.vstack(
                rx.text(
                    "Promote as new main campus:",
                    font_size="0.85rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                ),
                rx.select.root(
                    rx.select.trigger(placeholder="Select new main campus"),
                    rx.select.content(
                        rx.foreach(
                            AdminDepartmentsState.promote_candidates,
                            lambda c: rx.select.item(c["campus_code"], value=c["campus_id"]),
                        ),
                    ),
                    value=AdminDepartmentsState.promote_new_campus_id,
                    on_change=AdminDepartmentsState.set_promote_new_campus_id,
                    width="100%",
                ),
                align="start",
                gap="0.5rem",
                width="100%",
            ),
            rx.hstack(
                primary_btn(
                    "Remove & Promote",
                    on_click=AdminDepartmentsState.promote_and_remove_main_campus,
                    type="button",
                ),
                secondary_btn(
                    "Cancel",
                    on_click=AdminDepartmentsState.cancel_promote_remove,
                    type="button",
                ),
                gap="0.75rem",
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        is_open=AdminDepartmentsState.confirm_promote_remove_open,
        max_width="480px",
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
                config_toast(
                    AdminDepartmentsState.flash,
                    AdminDepartmentsState.flash_type,
                    AdminDepartmentsState.dismiss_flash,
                ),
                _inline_form(),
                _detail_panel(),
                _promote_remove_modal(),
                rx.cond(
                    AdminDepartmentsState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=AdminDepartmentsState.departments,
                        columns=[
                            TableColumn(key="code", label="Code"),
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="school_code", label="School"),
                            # Bug C: show main campus code; stay ≤4 cols (Tier-1 rule).
                            TableColumn(
                                key="main_campus_code",
                                label="Main Campus",
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
                id="dept-page-top",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
