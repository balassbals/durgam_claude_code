"""New NOC request form (/faculty/requests/new)."""

import reflex as rx

from durgam.pages.components import (
    flash_error,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.file_upload import file_upload_zone
from durgam.states.auth import AuthState
from durgam.states.faculty_requests import NewFacultyRequestState

DOWNLOAD_PREFIX = "/api/files/"


def _attached_file_item(f: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.icon("file", size=14, color="var(--color-muted)"),
        rx.text(f["name"], font_size="0.85rem", color="var(--color-body)"),
        rx.text(
            rx.Var.create("(") + f["size_kb"].to(str) + " KB)",
            font_size="0.8rem",
            color="var(--color-muted)",
        ),
        rx.icon_button(
            rx.icon("x", size=12),
            aria_label="Remove attachment",
            on_click=NewFacultyRequestState.remove_attachment(f["id"]),
            variant="ghost",
            size="1",
            cursor="pointer",
            color="var(--color-muted)",
        ),
        align="center",
        gap="0.5rem",
        padding="0.25rem 0",
    )


def _upload_section() -> rx.Component:
    return rx.cond(
        NewFacultyRequestState.can_upload,
        rx.vstack(
            rx.text(
                "Supporting Documents (optional)",
                font_weight="600",
                font_size="0.9rem",
                font_family="var(--font-sans)",
            ),
            rx.text(
                "Attach any supporting documents (PDF, PNG, JPEG).",
                font_size="0.8rem",
                color="var(--color-muted)",
                font_family="var(--font-sans)",
            ),
            rx.cond(
                NewFacultyRequestState.attached_files.length() > 0,  # type: ignore[attr-defined]
                rx.vstack(
                    rx.foreach(NewFacultyRequestState.attached_files, _attached_file_item),
                    align="start",
                    gap="0",
                    width="100%",
                ),
                rx.fragment(),
            ),
            file_upload_zone(
                on_drop=NewFacultyRequestState.handle_upload(rx.upload_files()),  # type: ignore[arg-type]
                label="Drag & drop files, or click to browse",
                accept={"application/pdf": [".pdf"], "image/png": [".png"], "image/jpeg": [".jpg", ".jpeg"]},
            ),
            align="start",
            gap="0.5rem",
            width="100%",
        ),
        rx.box(
            rx.text(
                "Initialising form…",
                font_size="0.85rem",
                color="var(--color-muted)",
            ),
            border="2px dashed var(--color-rule)",
            border_radius="8px",
            padding="1.5rem",
            width="100%",
            text_align="center",
            opacity="0.5",
        ),
    )


def faculty_requests_new_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link(
                    secondary_btn(rx.icon("arrow-left", size=14), " Back"),
                    href="/faculty/requests",
                    text_decoration="none",
                ),
                margin_bottom="1rem",
            ),
            rx.heading(
                "New NOC Request",
                size="5",
                font_family="var(--font-sans)",
                margin_bottom="1.5rem",
            ),
            rx.cond(
                NewFacultyRequestState.form_error != "",
                flash_error(NewFacultyRequestState.form_error),
                rx.fragment(),
            ),
            rx.form(
                rx.vstack(
                    rx.vstack(
                        rx.text(
                            "Purpose *",
                            font_weight="600",
                            font_size="0.9rem",
                            font_family="var(--font-sans)",
                        ),
                        rx.text_area(
                            placeholder="Describe the purpose of this NOC",
                            value=NewFacultyRequestState.purpose,
                            on_change=NewFacultyRequestState.set_purpose,
                            rows="3",
                            width="100%",
                            font_family="var(--font-sans)",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "To Whom *",
                            font_weight="600",
                            font_size="0.9rem",
                            font_family="var(--font-sans)",
                        ),
                        rx.input(
                            placeholder="Organisation or authority this NOC is addressed to",
                            value=NewFacultyRequestState.to_whom,
                            on_change=NewFacultyRequestState.set_to_whom,
                            width="100%",
                            font_family="var(--font-sans)",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Date Required By",
                            font_weight="600",
                            font_size="0.9rem",
                            font_family="var(--font-sans)",
                        ),
                        rx.input(
                            type="date",
                            value=NewFacultyRequestState.date_required_by,
                            on_change=NewFacultyRequestState.set_date_required_by,
                            width="100%",
                            font_family="var(--font-sans)",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text(
                            "Additional Notes",
                            font_weight="600",
                            font_size="0.9rem",
                            font_family="var(--font-sans)",
                        ),
                        rx.text_area(
                            placeholder="Any additional information (optional)",
                            value=NewFacultyRequestState.additional_notes,
                            on_change=NewFacultyRequestState.set_additional_notes,
                            rows="3",
                            width="100%",
                            font_family="var(--font-sans)",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    _upload_section(),
                    rx.hstack(
                        primary_btn(
                            "Submit Request",
                            type="submit",
                            disabled=NewFacultyRequestState.submit_disabled,
                            loading=NewFacultyRequestState.submitting,
                        ),
                        secondary_btn(
                            "Cancel",
                            on_click=rx.redirect("/faculty/requests"),
                            type="button",
                        ),
                        gap="0.75rem",
                        margin_top="0.5rem",
                    ),
                    gap="1rem",
                    width="100%",
                    align="start",
                ),
                on_submit=NewFacultyRequestState.submit_request,
                reset_on_submit=False,
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

    return rx.cond(AuthState.current_user_id != "", content, rx.fragment())
