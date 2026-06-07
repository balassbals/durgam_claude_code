"""Non-regular faculty management page — /admin/config/non-regular-faculty."""

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
from durgam.states.config_non_regular_faculty import (
    NonRegularFacultyConfigState,
    _TYPE_OPTIONS,
)


def _approval_cell(row: dict) -> rx.Component:
    return rx.cond(
        NonRegularFacultyConfigState.can_approve,
        rx.box(
            rx.cond(
                row["approved"] == "yes",
                rx.tooltip(
                    rx.badge(
                        "Approved",
                        color_scheme="green",
                        variant="soft",
                        cursor="pointer",
                        on_click=NonRegularFacultyConfigState.toggle_approval(  # type: ignore[call-arg, func-returns-value]
                            row["id"], row["approved"]
                        ),
                    ),
                    content=row["approved_info"],
                ),
                rx.badge(
                    "Pending",
                    color_scheme="amber",
                    variant="soft",
                    cursor="pointer",
                    on_click=NonRegularFacultyConfigState.toggle_approval(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["approved"]
                    ),
                ),
            ),
        ),
        rx.cond(
            row["approved"] == "yes",
            rx.tooltip(
                rx.badge("Approved", color_scheme="green", variant="soft"),
                content=row["approved_info"],
            ),
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
                    on_click=NonRegularFacultyConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["name"], row["designation"],
                        row["organization"], row["expertise"],
                        row["available_from"], row["available_to"],
                        row["non_regular_type"],
                    ),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=NonRegularFacultyConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
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
        rx.cond(
            NonRegularFacultyConfigState.dept_locked,
            rx.text(NonRegularFacultyConfigState.dept_name_display,
                    font_weight="600", font_size="0.9rem"),
            rx.select.root(
                rx.select.trigger(placeholder="Select department"),
                rx.select.content(
                    rx.foreach(
                        NonRegularFacultyConfigState.dept_options,
                        lambda o: rx.select.item(o["label"], value=o["value"]),
                    ),
                ),
                value=NonRegularFacultyConfigState.selected_dept_id,
                on_change=NonRegularFacultyConfigState.on_dept_change,
                width="320px",
            ),
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    NonRegularFacultyConfigState.editing_id == "",
                    "New Non-Regular Faculty",
                    "Edit Non-Regular Faculty",
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
                        value=NonRegularFacultyConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Type *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select type"),
                            rx.select.content(
                                rx.foreach(
                                    _TYPE_OPTIONS,
                                    lambda o: rx.select.item(o, value=o),
                                ),
                            ),
                            value=NonRegularFacultyConfigState.form_type,
                            on_change=NonRegularFacultyConfigState.set_form_type,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=NonRegularFacultyConfigState.form_name,
                            on_change=NonRegularFacultyConfigState.set_form_name,
                            placeholder="Full name",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Designation *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_designation",
                            value=NonRegularFacultyConfigState.form_designation,
                            on_change=NonRegularFacultyConfigState.set_form_designation,
                            placeholder="e.g. Professor",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Organization *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_organization",
                            value=NonRegularFacultyConfigState.form_organization,
                            on_change=NonRegularFacultyConfigState.set_form_organization,
                            placeholder="e.g. IISc Bangalore",
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Expertise *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_expertise",
                            value=NonRegularFacultyConfigState.form_expertise,
                            on_change=NonRegularFacultyConfigState.set_form_expertise,
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
                            value=NonRegularFacultyConfigState.form_available_from,
                            on_change=NonRegularFacultyConfigState.set_form_available_from,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.vstack(
                        rx.text("Available To *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_available_to",
                            type="date",
                            value=NonRegularFacultyConfigState.form_available_to,
                            on_change=NonRegularFacultyConfigState.set_form_available_to,
                            width="100%",
                        ),
                        align="start", gap="0.25rem", width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=NonRegularFacultyConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    rx.text(
                        "New entries appear as Pending. An authorized approver "
                        "(Director or Registrar family) must approve before the "
                        "appointment is institutionally recognized. The Approval "
                        "Requests module in a future milestone will configure "
                        "case-by-case routing between Director and Registrar.",
                        font_size="0.75rem",
                        color="var(--color-muted)",
                        font_style="italic",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=NonRegularFacultyConfigState.save_visitor,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=NonRegularFacultyConfigState.show_form,
    )


def _pending_request_action(row: dict) -> rx.Component:
    return rx.icon_button(
        rx.icon("eye", size=14),
        aria_label="View request",
        variant="ghost",
        size="1",
        cursor="pointer",
        on_click=rx.redirect(rx.cond(True, "/approvals/request/" + row["id"], "")),  # type: ignore[arg-type]
    )


def _pending_approvals_section() -> rx.Component:
    return rx.cond(
        NonRegularFacultyConfigState.pending_requests.length() > 0,  # type: ignore[attr-defined]
        rx.vstack(
            rx.heading(
                "Pending Approvals",
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="0.5rem",
            ),
            data_table(
                rows=NonRegularFacultyConfigState.pending_requests,
                columns=[
                    TableColumn(key="title", label="Title"),
                    TableColumn(key="requestor_display", label="Requestor"),
                    TableColumn(key="stage_label", label="Stage", hidden_on_card=True),
                    TableColumn(key="submitted_at", label="Submitted", hidden_on_card=True),
                ],
                card_primary_key="title",
                is_mobile=False,
                actions=_pending_request_action,
                empty_message="No pending non-regular-faculty approvals.",
            ),
            rx.separator(margin_y="1.5rem"),
            align="start",
            width="100%",
            margin_bottom="1rem",
        ),
        rx.fragment(),
    )


def admin_config_non_regular_faculty() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Non-Regular Faculty",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    primary_btn(
                        "+ Submit for Approval",
                        on_click=rx.redirect("/approvals/submit"),
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
                    NonRegularFacultyConfigState.flash,
                    NonRegularFacultyConfigState.flash_type,
                    NonRegularFacultyConfigState.dismiss_flash,
                ),
                _inline_form(),
                _pending_approvals_section(),
                rx.cond(
                    NonRegularFacultyConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=NonRegularFacultyConfigState.visitors,
                        columns=[
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="non_regular_type", label="Type"),
                            TableColumn(key="designation", label="Designation"),
                            TableColumn(key="organization", label="Organization"),
                            TableColumn(key="expertise", label="Expertise"),
                            TableColumn(key="available_from", label="From"),
                            TableColumn(key="available_to", label="To"),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No non-regular faculty records found.",
                    ),
                ),
                confirmation_dialog(
                    is_open=NonRegularFacultyConfigState.confirm_open,
                    title=NonRegularFacultyConfigState.confirm_title,
                    body=NonRegularFacultyConfigState.confirm_body,
                    on_confirm=NonRegularFacultyConfigState.soft_delete_visitor,
                    on_cancel=NonRegularFacultyConfigState.cancel_confirm,
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
