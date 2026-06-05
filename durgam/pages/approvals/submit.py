"""Submit a new approval request (/approvals/submit)."""

import reflex as rx

from durgam.pages.components import (
    flash_error,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.file_upload import file_upload_zone
from durgam.states.approval_requests import SubmitRequestState
from durgam.states.auth import AuthState


def _process_option(opt: rx.Var) -> rx.Component:
    return rx.select.item(opt["title"], value=opt["id"])


def _uploaded_file_item(file_id: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.icon("file", size=14, color="var(--color-muted)"),
        rx.text(file_id, font_size="0.85rem", color="var(--color-body)"),
        rx.icon_button(
            rx.icon("x", size=12),
            aria_label="Remove file",
            on_click=SubmitRequestState.remove_file(file_id),
            variant="ghost",
            size="1",
            cursor="pointer",
            color="var(--color-muted)",
        ),
        align="center",
        gap="0.5rem",
        padding="0.25rem 0",
    )


def _attachment_section() -> rx.Component:
    return rx.cond(
        SubmitRequestState.selected_process_id != "none",
        rx.vstack(
            rx.text(
                "Attachments",
                font_weight="600",
                font_size="0.9rem",
                font_family="var(--font-sans)",
            ),
            rx.cond(
                SubmitRequestState.requires_upward,
                rx.text(
                    rx.cond(
                        SubmitRequestState.max_upward > 0,
                        f"This process requires 1–{SubmitRequestState.max_upward} supporting document(s).",
                        "This process requires at least 1 supporting document.",
                    ),
                    font_size="0.8rem",
                    color="var(--color-muted)",
                    font_family="var(--font-sans)",
                ),
                rx.cond(
                    SubmitRequestState.max_upward > 0,
                    rx.text(
                        f"You may attach up to {SubmitRequestState.max_upward} document(s).",
                        font_size="0.8rem",
                        color="var(--color-muted)",
                        font_family="var(--font-sans)",
                    ),
                    rx.text(
                        "Attachments are optional.",
                        font_size="0.8rem",
                        color="var(--color-muted)",
                        font_family="var(--font-sans)",
                    ),
                ),
            ),
            rx.cond(
                SubmitRequestState.uploaded_file_ids.length() > 0,  # type: ignore[attr-defined]
                rx.vstack(
                    rx.foreach(
                        SubmitRequestState.uploaded_file_ids,
                        _uploaded_file_item,
                    ),
                    rx.text(
                        f"{SubmitRequestState.uploaded_file_ids.length()} file(s) attached",  # type: ignore[attr-defined]
                        font_size="0.8rem",
                        color="var(--color-muted)",
                    ),
                    align="start",
                    gap="0",
                    width="100%",
                ),
                rx.fragment(),
            ),
            file_upload_zone(
                on_drop=SubmitRequestState.handle_upload(rx.upload_files()),  # type: ignore[arg-type]
                label="Drag & drop files here, or click to browse",
            ),
            align="start",
            gap="0.5rem",
            width="100%",
        ),
        rx.fragment(),
    )


_NRF_TYPE_OPTIONS = ["visiting", "adjunct", "guest", "contract", "honorary"]


def _nrf_fields_section() -> rx.Component:
    return rx.cond(
        SubmitRequestState.selected_process_code == "NRF_APPROVAL",
        rx.vstack(
            rx.text(
                "Non-Regular Faculty Details",
                font_weight="600",
                font_size="0.9rem",
                font_family="var(--font-sans)",
            ),
            rx.vstack(
                rx.text("Name *", font_size="0.85rem", color="var(--color-muted)"),
                rx.input(
                    placeholder="Full name",
                    value=SubmitRequestState.nrf_name,
                    on_change=SubmitRequestState.set_nrf_name,
                    width="100%",
                ),
                align="start", gap="0.25rem", width="100%",
            ),
            rx.vstack(
                rx.text("Designation *", font_size="0.85rem", color="var(--color-muted)"),
                rx.input(
                    placeholder="e.g. Professor",
                    value=SubmitRequestState.nrf_designation,
                    on_change=SubmitRequestState.set_nrf_designation,
                    width="100%",
                ),
                align="start", gap="0.25rem", width="100%",
            ),
            rx.vstack(
                rx.text("Organization *", font_size="0.85rem", color="var(--color-muted)"),
                rx.input(
                    placeholder="e.g. IISc Bangalore",
                    value=SubmitRequestState.nrf_organization,
                    on_change=SubmitRequestState.set_nrf_organization,
                    width="100%",
                ),
                align="start", gap="0.25rem", width="100%",
            ),
            rx.vstack(
                rx.text("Expertise *", font_size="0.85rem", color="var(--color-muted)"),
                rx.input(
                    placeholder="e.g. Quantum Physics",
                    value=SubmitRequestState.nrf_expertise,
                    on_change=SubmitRequestState.set_nrf_expertise,
                    width="100%",
                ),
                align="start", gap="0.25rem", width="100%",
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("Available From *", font_size="0.85rem", color="var(--color-muted)"),
                    rx.input(
                        type="date",
                        value=SubmitRequestState.nrf_available_from,
                        on_change=SubmitRequestState.set_nrf_available_from,
                        width="100%",
                    ),
                    align="start", gap="0.25rem", flex="1",
                ),
                rx.vstack(
                    rx.text("Available To *", font_size="0.85rem", color="var(--color-muted)"),
                    rx.input(
                        type="date",
                        value=SubmitRequestState.nrf_available_to,
                        on_change=SubmitRequestState.set_nrf_available_to,
                        width="100%",
                    ),
                    align="start", gap="0.25rem", flex="1",
                ),
                gap="1rem", width="100%",
            ),
            rx.vstack(
                rx.text("Type", font_size="0.85rem", color="var(--color-muted)"),
                rx.select.root(
                    rx.select.trigger(placeholder="Select type"),
                    rx.select.content(
                        rx.foreach(
                            _NRF_TYPE_OPTIONS,
                            lambda o: rx.select.item(o, value=o),
                        ),
                    ),
                    value=SubmitRequestState.nrf_type,
                    on_change=SubmitRequestState.set_nrf_type,
                    width="100%",
                ),
                align="start", gap="0.25rem", width="100%",
            ),
            align="start",
            gap="0.75rem",
            width="100%",
            padding="1rem",
            background="var(--color-background, #f5f0eb)",
            border="1px solid var(--color-rule)",
            border_radius="6px",
        ),
        rx.fragment(),
    )


def submit_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.heading(
                "New Approval Request",
                size="5",
                font_family="var(--font-sans)",
                margin_bottom="1.5rem",
            ),
            # Error banner
            rx.cond(
                SubmitRequestState.error != "",
                flash_error(SubmitRequestState.error),
                rx.fragment(),
            ),
            # Form
            rx.vstack(
                # Process picker
                rx.vstack(
                    rx.text(
                        "Approval Process",
                        font_weight="600",
                        font_size="0.9rem",
                        font_family="var(--font-sans)",
                    ),
                    rx.select.root(
                        rx.select.trigger(
                            placeholder="Select an approval process",
                        ),
                        rx.select.content(
                            rx.select.item("Select a process…", value="none"),
                            rx.foreach(
                                SubmitRequestState.process_options,
                                _process_option,
                            ),
                        ),
                        value=SubmitRequestState.selected_process_id,
                        on_change=SubmitRequestState.on_process_change,
                        size="2",
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Title
                rx.vstack(
                    rx.text(
                        "Title",
                        font_weight="600",
                        font_size="0.9rem",
                        font_family="var(--font-sans)",
                    ),
                    rx.input(
                        placeholder="Brief title for your request",
                        value=SubmitRequestState.title,
                        on_change=SubmitRequestState.set_title,
                        max_length=255,
                        width="100%",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # Description
                rx.vstack(
                    rx.text(
                        "Description",
                        font_weight="600",
                        font_size="0.9rem",
                        font_family="var(--font-sans)",
                    ),
                    rx.text_area(
                        placeholder="Provide additional details (optional)",
                        value=SubmitRequestState.description,
                        on_change=SubmitRequestState.set_description,
                        width="100%",
                        rows="4",
                    ),
                    align="start",
                    gap="0.25rem",
                    width="100%",
                ),
                # NRF-specific fields (conditional)
                _nrf_fields_section(),
                # Attachments
                _attachment_section(),
                # Action buttons
                rx.hstack(
                    secondary_btn(
                        "Cancel",
                        on_click=rx.redirect("/approvals/my-requests"),
                        type="button",
                    ),
                    primary_btn(
                        rx.cond(
                            SubmitRequestState.submitting,
                            rx.hstack(
                                rx.spinner(size="1"),
                                rx.text("Submitting…"),
                                align="center",
                                gap="0.5rem",
                            ),
                            rx.text("Submit Request"),
                        ),
                        on_click=SubmitRequestState.submit_request,
                        disabled=SubmitRequestState.submit_disabled,
                    ),
                    justify="end",
                    gap="0.75rem",
                    width="100%",
                    margin_top="1rem",
                ),
                align="start",
                gap="1.25rem",
                width="100%",
                padding="1.5rem",
                background="white",
                border="1px solid var(--color-rule)",
                border_radius="6px",
            ),
            padding="2rem",
            max_width="680px",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    )

    return rx.cond(
        AuthState.current_user_id != "",
        content,
        rx.fragment(),
    )
