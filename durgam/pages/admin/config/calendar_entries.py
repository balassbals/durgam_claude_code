"""Calendar entry management page — /admin/config/calendar."""

import reflex as rx

from durgam.pages.components import (
    admin_page,
    config_toast,
    destructive_btn,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_calendar_entry import CalendarEntryConfigState


def _kebab(row: dict) -> rx.Component:
    is_owner = row["is_owner"] == "1"
    return rx.cond(
        CalendarEntryConfigState.ay_is_locked,
        rx.text("🔒", font_size="0.8rem", color="var(--color-muted)"),
        rx.cond(
            is_owner,
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
                        on_click=CalendarEntryConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                            row["id"], row["title"], row["type_raw"],
                            row["starts_at"], row["ends_at"], row["notes"],
                        ),
                    ),
                    rx.menu.item(
                        "Delete",
                        on_click=CalendarEntryConfigState.open_delete_confirm(  # type: ignore[call-arg, func-returns-value]
                            row["id"], row["title"],
                        ),
                        color="var(--color-danger, #c0392b)",
                    ),
                ),
            ),
            rx.fragment(),
        ),
    )


def _ay_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Academic Year:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select academic year"),
            rx.select.content(
                rx.foreach(
                    CalendarEntryConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=CalendarEntryConfigState.selected_ay_id,
            on_change=CalendarEntryConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            CalendarEntryConfigState.ay_is_locked,
            rx.badge("AY Locked", color_scheme="red", variant="soft"),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _phase_indicator() -> rx.Component:
    """Three-phase collaboration chain status badges."""
    return rx.hstack(
        rx.cond(
            CalendarEntryConfigState.master_calendar_locked,
            rx.badge("Registrar Confirmed", color_scheme="green", variant="soft"),
            rx.badge("Phase 1: Registrar", color_scheme="blue", variant="soft"),
        ),
        rx.cond(
            CalendarEntryConfigState.master_calendar_locked,
            rx.cond(
                CalendarEntryConfigState.iqac_confirmed,
                rx.badge("IQAC Confirmed", color_scheme="green", variant="soft"),
                rx.badge("Phase 2: IQAC", color_scheme="amber", variant="soft"),
            ),
            rx.badge("IQAC: Waiting", color_scheme="gray", variant="soft"),
        ),
        rx.cond(
            CalendarEntryConfigState.iqac_confirmed,
            rx.badge("Phase 3: Open", color_scheme="green", variant="soft"),
            rx.badge("Others: Waiting", color_scheme="gray", variant="soft"),
        ),
        align="center",
        gap="0.5rem",
        flex_wrap="wrap",
    )


def _filter_bar() -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text("Type:", font_size="0.85rem", color="var(--color-muted)"),
            rx.select.root(
                rx.select.trigger(placeholder="All types"),
                rx.select.content(
                    rx.select.item("All", value="all"),
                    rx.select.item("Semester Begin", value="sem_begin"),
                    rx.select.item("Semester End", value="sem_end"),
                    rx.select.item("Holiday", value="holiday"),
                    rx.select.item("Class Suspension", value="class_suspension"),
                    rx.select.item("CIE", value="cie"),
                    rx.select.item("End Semester Exam", value="end_sem_exam"),
                    rx.select.item("Admission Exam", value="admission_exam"),
                    rx.select.item("PhD Admission", value="phd_admission"),
                    rx.select.item("Winter Vacation", value="winter_vacation"),
                    rx.select.item("Summer Vacation", value="summer_vacation"),
                    rx.select.item("Academic Council", value="academic_council_meeting"),
                    rx.select.item("Finance Committee", value="finance_committee_meeting"),
                    rx.select.item("Executive Committee", value="executive_committee_meeting"),
                    rx.select.item("Activity (IQAC)", value="activity"),
                    rx.select.item("Sports", value="sports"),
                    rx.select.item("Cultural", value="cultural"),
                    rx.select.item("Academic Activity", value="academic_activity"),
                    rx.select.item("Other Activity", value="other_activity"),
                ),
                value=CalendarEntryConfigState.filter_type,
                on_change=CalendarEntryConfigState.on_filter_type_change,
                width="200px",
            ),
            rx.text("From:", font_size="0.85rem", color="var(--color-muted)"),
            rx.input(
                type="date",
                value=CalendarEntryConfigState.filter_date_from,
                on_change=CalendarEntryConfigState.on_filter_date_from_change,
                width="150px",
            ),
            rx.text("To:", font_size="0.85rem", color="var(--color-muted)"),
            rx.input(
                type="date",
                value=CalendarEntryConfigState.filter_date_to,
                on_change=CalendarEntryConfigState.on_filter_date_to_change,
                width="150px",
            ),
            rx.text("Owner:", font_size="0.85rem", color="var(--color-muted)"),
            rx.select.root(
                rx.select.trigger(placeholder="All roles"),
                rx.select.content(
                    rx.select.item("All", value="all"),
                    rx.foreach(
                        CalendarEntryConfigState.owner_role_options,
                        lambda o: rx.select.item(o["label"], value=o["value"]),
                    ),
                ),
                value=CalendarEntryConfigState.filter_owner_role,
                on_change=CalendarEntryConfigState.on_filter_owner_role_change,
                width="180px",
            ),
            secondary_btn(
                "Clear filters",
                on_click=CalendarEntryConfigState.clear_filters,
                size="1",
            ),
            align="center",
            gap="0.5rem",
            flex_wrap="wrap",
        ),
        width="100%",
    )


def _export_bar() -> rx.Component:
    return rx.hstack(
        rx.text("Export:", font_size="0.85rem", color="var(--color-muted)"),
        secondary_btn("CSV", on_click=CalendarEntryConfigState.export_csv, size="1"),
        secondary_btn("Excel", on_click=CalendarEntryConfigState.export_excel, size="1"),
        secondary_btn("PDF", on_click=CalendarEntryConfigState.export_pdf, size="1"),
        secondary_btn("DOCX", on_click=CalendarEntryConfigState.export_docx, size="1"),
        align="center",
        gap="0.5rem",
    )


def _action_buttons() -> rx.Component:
    """Lock Master Calendar and IQAC Confirm buttons, conditionally shown."""
    return rx.hstack(
        # Registrar: "Confirm Registrar Calendar" — visible when master not yet locked
        rx.cond(
            CalendarEntryConfigState.can_configure_ay
            & ~CalendarEntryConfigState.master_calendar_locked
            & ~CalendarEntryConfigState.ay_is_locked,
            destructive_btn(
                "Confirm Registrar Calendar",
                on_click=CalendarEntryConfigState.open_lock_master_confirm,
            ),
            rx.fragment(),
        ),
        # IQAC: "Confirm IQAC Calendar" — visible when master locked but IQAC not confirmed
        rx.cond(
            CalendarEntryConfigState.can_confirm_iqac
            & CalendarEntryConfigState.master_calendar_locked
            & ~CalendarEntryConfigState.iqac_confirmed
            & ~CalendarEntryConfigState.ay_is_locked,
            destructive_btn(
                "Confirm IQAC Calendar",
                on_click=CalendarEntryConfigState.open_iqac_confirm,
            ),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    CalendarEntryConfigState.editing_id == "",
                    "New Calendar Entry",
                    "Edit Calendar Entry",
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
                        value=CalendarEntryConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Title", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_title",
                            value=CalendarEntryConfigState.form_title,
                            on_change=CalendarEntryConfigState.set_form_title,
                            placeholder="Entry title",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.cond(
                        CalendarEntryConfigState.editing_id == "",
                        rx.vstack(
                            rx.text("Type", font_size="0.85rem", color="var(--color-muted)"),
                            rx.select.root(
                                rx.select.trigger(placeholder="Select entry type"),
                                rx.select.content(
                                    rx.foreach(
                                        CalendarEntryConfigState.allowed_type_options,
                                        lambda o: rx.select.item(o["label"], value=o["value"]),
                                    ),
                                ),
                                value=CalendarEntryConfigState.form_entry_type,
                                on_change=CalendarEntryConfigState.set_form_entry_type,
                                width="100%",
                            ),
                            rx.input(
                                type="hidden",
                                name="form_entry_type",
                                value=CalendarEntryConfigState.form_entry_type,
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                        rx.vstack(
                            rx.text("Type", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                value=CalendarEntryConfigState.form_entry_type,
                                disabled=True,
                                width="100%",
                            ),
                            rx.input(
                                type="hidden",
                                name="form_entry_type",
                                value=CalendarEntryConfigState.form_entry_type,
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Starts At", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                type="datetime-local",
                                name="form_starts_at",
                                value=CalendarEntryConfigState.form_starts_at,
                                on_change=CalendarEntryConfigState.set_form_starts_at,
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            flex="1",
                        ),
                        rx.vstack(
                            rx.text("Ends At", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                type="datetime-local",
                                name="form_ends_at",
                                value=CalendarEntryConfigState.form_ends_at,
                                on_change=CalendarEntryConfigState.set_form_ends_at,
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            flex="1",
                        ),
                        gap="1rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Notes (optional)", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            name="form_notes",
                            value=CalendarEntryConfigState.form_notes,
                            on_change=CalendarEntryConfigState.set_form_notes,
                            placeholder="Additional notes",
                            width="100%",
                            rows="3",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=CalendarEntryConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=CalendarEntryConfigState.save_entry,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=CalendarEntryConfigState.show_form,
        max_width="600px",
    )


def admin_config_calendar() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.hstack(
                    rx.heading(
                        "Academic Calendar",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        CalendarEntryConfigState.ay_is_locked,
                        rx.fragment(),
                        primary_btn(
                            "+ New Entry",
                            on_click=CalendarEntryConfigState.open_create,
                        ),
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                _ay_selector(),
                rx.box(height="0.5rem"),
                _phase_indicator(),
                rx.box(height="0.5rem"),
                _filter_bar(),
                rx.box(height="0.5rem"),
                rx.hstack(
                    _export_bar(),
                    rx.spacer(),
                    _action_buttons(),
                    align="center",
                    width="100%",
                ),
                rx.box(height="1rem"),
                config_toast(
                    CalendarEntryConfigState.flash,
                    CalendarEntryConfigState.flash_type,
                    CalendarEntryConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    CalendarEntryConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=CalendarEntryConfigState.entries,
                        columns=[
                            TableColumn(key="title", label="Title"),
                            TableColumn(key="type", label="Type"),
                            TableColumn(key="starts_at", label="Starts"),
                            TableColumn(key="ends_at", label="Ends"),
                            TableColumn(key="owner_role", label="Owner Role"),
                        ],
                        card_primary_key="title",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No calendar entries found.",
                    ),
                ),
                # Delete entry confirmation
                confirmation_dialog(
                    is_open=CalendarEntryConfigState.confirm_open,
                    title=CalendarEntryConfigState.confirm_title,
                    body=CalendarEntryConfigState.confirm_body,
                    on_confirm=CalendarEntryConfigState.soft_delete_entry,
                    on_cancel=CalendarEntryConfigState.cancel_confirm,
                    confirm_label="Delete",
                ),
                # Lock master calendar (Registrar confirm) confirmation
                confirmation_dialog(
                    is_open=CalendarEntryConfigState.lock_confirm_open,
                    title=CalendarEntryConfigState.confirm_title,
                    body=CalendarEntryConfigState.confirm_body,
                    on_confirm=CalendarEntryConfigState.lock_master_calendar,
                    on_cancel=CalendarEntryConfigState.cancel_lock_master,
                    confirm_label="Confirm",
                ),
                # IQAC confirm confirmation
                confirmation_dialog(
                    is_open=CalendarEntryConfigState.iqac_confirm_open,
                    title=CalendarEntryConfigState.confirm_title,
                    body=CalendarEntryConfigState.confirm_body,
                    on_confirm=CalendarEntryConfigState.confirm_iqac,
                    on_cancel=CalendarEntryConfigState.cancel_iqac_confirm,
                    confirm_label="Confirm",
                ),
                padding="2rem",
                max_width="1200px",
                width="100%",
                id="calendar-page-top",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        )
    )
