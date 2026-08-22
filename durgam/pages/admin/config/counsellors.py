"""Mental health counsellor management page — /admin/config/counsellors."""

import reflex as rx

from durgam.api import DOWNLOAD_PREFIX
from durgam.pages.components import (
    admin_page,
    app_shell,
    config_toast,
    form_modal,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.pages.shared.file_upload import file_upload_zone
from durgam.states.config_counsellor import CounsellorConfigState


def _kebab(row: dict) -> rx.Component:
    return rx.cond(
        CounsellorConfigState.ay_is_locked,
        rx.text("\U0001f512", font_size="0.8rem", color="var(--color-muted)"),
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
                    on_click=CounsellorConfigState.open_edit(  # type: ignore[call-arg, func-returns-value]
                        row["id"],
                        row["name"],
                        row["qualification"],
                        row["specialisation"],
                        row["mode"],
                        row["start"],
                        row["end"],
                        row["phone"],
                        row["email"],
                        row["display_order"],
                    ),
                ),
                rx.cond(
                    row["appt_file_id"] != "",
                    rx.menu.item(
                        "Download Appointment Letter",
                        on_click=rx.redirect(
                            DOWNLOAD_PREFIX + "/api/files/" + row["appt_file_id"],
                        ),
                    ),
                    rx.fragment(),
                ),
                rx.cond(
                    row["qual_file_id"] != "",
                    rx.menu.item(
                        "Download Qualification Proof",
                        on_click=rx.redirect(
                            DOWNLOAD_PREFIX + "/api/files/" + row["qual_file_id"],
                        ),
                    ),
                    rx.fragment(),
                ),
                rx.menu.item(
                    "Deactivate",
                    on_click=CounsellorConfigState.open_deactivate_confirm(  # type: ignore[call-arg, func-returns-value]
                        row["id"], row["name"]
                    ),
                    color="var(--color-danger, #c0392b)",
                ),
            ),
        ),
    )


def _ay_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Academic Year:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select academic year"),
            rx.select.content(
                rx.foreach(
                    CounsellorConfigState.ay_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=CounsellorConfigState.selected_ay_id,
            on_change=CounsellorConfigState.on_ay_change,
            width="200px",
        ),
        rx.cond(
            CounsellorConfigState.ay_is_locked,
            rx.badge("AY Locked", color_scheme="red", variant="soft"),
            rx.fragment(),
        ),
        align="center",
        gap="0.75rem",
    )


def _campus_selector() -> rx.Component:
    return rx.hstack(
        rx.text("Campus:", font_size="0.85rem", color="var(--color-muted)"),
        rx.select.root(
            rx.select.trigger(placeholder="Select campus"),
            rx.select.content(
                rx.foreach(
                    CounsellorConfigState.campus_options,
                    lambda o: rx.select.item(o["label"], value=o["value"]),
                ),
            ),
            value=CounsellorConfigState.selected_campus_id,
            on_change=CounsellorConfigState.on_campus_change,
            width="280px",
        ),
        align="center",
        gap="0.75rem",
    )


def _inline_form() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    CounsellorConfigState.editing_id == "",
                    "New Counsellor",
                    "Edit Counsellor",
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
                        value=CounsellorConfigState.editing_id,
                    ),
                    rx.vstack(
                        rx.text("Name *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_name",
                            value=CounsellorConfigState.form_name,
                            on_change=CounsellorConfigState.set_form_name,
                            placeholder="Counsellor name",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Qualification *", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_qualification",
                            value=CounsellorConfigState.form_qualification,
                            on_change=CounsellorConfigState.set_form_qualification,
                            placeholder="e.g. PhD Clinical Psychology",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Specialisation *", font_size="0.85rem", color="var(--color-muted)"
                        ),
                        rx.input(
                            name="form_specialisation",
                            value=CounsellorConfigState.form_specialisation,
                            on_change=CounsellorConfigState.set_form_specialisation,
                            placeholder="e.g. Clinical Psychology",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Mode of Appointment *", font_size="0.85rem", color="var(--color-muted)"
                        ),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select mode"),
                            rx.select.content(
                                rx.select.item("In-house", value="inhouse"),
                                rx.select.item("External", value="external"),
                            ),
                            name="form_mode",
                            value=CounsellorConfigState.form_mode,
                            on_change=CounsellorConfigState.set_form_mode,
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text(
                                "Start Date *", font_size="0.85rem", color="var(--color-muted)"
                            ),
                            rx.input(
                                type="date",
                                name="form_start",
                                value=CounsellorConfigState.form_start,
                                on_change=CounsellorConfigState.set_form_start,
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="50%",
                        ),
                        rx.vstack(
                            rx.text("End Date *", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                type="date",
                                name="form_end",
                                value=CounsellorConfigState.form_end,
                                on_change=CounsellorConfigState.set_form_end,
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="50%",
                        ),
                        width="100%",
                        gap="1rem",
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text("Phone", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                name="form_phone",
                                value=CounsellorConfigState.form_phone,
                                on_change=CounsellorConfigState.set_form_phone,
                                placeholder="+91-9876543210",
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="50%",
                        ),
                        rx.vstack(
                            rx.text("Email", font_size="0.85rem", color="var(--color-muted)"),
                            rx.input(
                                name="form_email",
                                value=CounsellorConfigState.form_email,
                                on_change=CounsellorConfigState.set_form_email,
                                placeholder="email@example.com",
                                width="100%",
                            ),
                            align="start",
                            gap="0.25rem",
                            width="50%",
                        ),
                        width="100%",
                        gap="1rem",
                    ),
                    rx.vstack(
                        rx.text("Display Order", font_size="0.85rem", color="var(--color-muted)"),
                        rx.input(
                            name="form_display_order",
                            type="number",
                            value=CounsellorConfigState.form_display_order,
                            on_change=CounsellorConfigState.set_form_display_order,
                            width="100px",
                        ),
                        rx.text(
                            "Lower numbers appear first",
                            font_size="0.75rem",
                            color="var(--color-muted)",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Appointment Letter (PDF, ≤2 MB)",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        file_upload_zone(
                            on_drop=CounsellorConfigState.stage_appt_letter,  # type: ignore[arg-type]
                            accept={"application/pdf": [".pdf"]},
                            label="Drag & drop appointment letter PDF, or click to browse",
                        ),
                        rx.cond(
                            CounsellorConfigState.staged_appt_letter_name != "",
                            rx.text(
                                CounsellorConfigState.staged_appt_letter_name,
                                font_size="0.8rem",
                                color="var(--color-success)",
                            ),
                            rx.fragment(),
                        ),
                        rx.text(
                            "Qualification Proof (PDF, ≤2 MB)",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                            margin_top="0.5rem",
                        ),
                        file_upload_zone(
                            on_drop=CounsellorConfigState.stage_qual_proof,  # type: ignore[arg-type]
                            accept={"application/pdf": [".pdf"]},
                            label="Drag & drop qualification proof PDF, or click to browse",
                        ),
                        rx.cond(
                            CounsellorConfigState.staged_qual_proof_name != "",
                            rx.text(
                                CounsellorConfigState.staged_qual_proof_name,
                                font_size="0.8rem",
                                color="var(--color-success)",
                            ),
                            rx.fragment(),
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=CounsellorConfigState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                    ),
                    gap="1rem",
                    align="start",
                    width="100%",
                ),
                on_submit=CounsellorConfigState.save_counsellor,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=CounsellorConfigState.show_form,
        max_width="620px",
    )


def admin_config_counsellors() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.heading(
                        "Mental Health Counsellors",
                        size="5",
                        font_family="var(--font-sans)",
                    ),
                    rx.spacer(),
                    rx.cond(
                        CounsellorConfigState.ay_is_locked,
                        rx.fragment(),
                        rx.hstack(
                            primary_btn(
                                "+ Add Counsellor",
                                on_click=CounsellorConfigState.open_create,
                            ),
                            secondary_btn(
                                "Export Roster",
                                on_click=CounsellorConfigState.export_roster,
                            ),
                            gap="0.5rem",
                        ),
                    ),
                    align="center",
                    width="100%",
                    margin_bottom="1rem",
                ),
                rx.hstack(
                    _ay_selector(),
                    _campus_selector(),
                    gap="1.5rem",
                    flex_wrap="wrap",
                ),
                rx.box(height="1rem"),
                config_toast(
                    CounsellorConfigState.flash,
                    CounsellorConfigState.flash_type,
                    CounsellorConfigState.dismiss_flash,
                ),
                _inline_form(),
                rx.cond(
                    CounsellorConfigState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    data_table(
                        rows=CounsellorConfigState.counsellors,
                        columns=[
                            TableColumn(key="name", label="Name"),
                            TableColumn(key="qualification", label="Qualification"),
                            TableColumn(key="specialisation", label="Specialisation"),
                            TableColumn(key="mode", label="Mode"),
                            TableColumn(key="period", label="Appointment Period"),
                        ],
                        card_primary_key="name",
                        is_mobile=False,
                        actions=_kebab,
                        empty_message="No counsellors found for this academic year and campus.",
                    ),
                ),
                confirmation_dialog(
                    is_open=CounsellorConfigState.confirm_open,
                    title=CounsellorConfigState.confirm_title,
                    body=CounsellorConfigState.confirm_body,
                    on_confirm=CounsellorConfigState.soft_delete_counsellor,
                    on_cancel=CounsellorConfigState.cancel_confirm,
                    confirm_label="Deactivate",
                ),
                align="start",
                width="100%",
            ),
            container="lg",
        )
    )
