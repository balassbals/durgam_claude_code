"""Faculty documents list page (/faculty/profile/documents) — M10 Phase P4.

PDF upload + multi-row list. File immutable post-upload (Edit = metadata only).
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import (
    app_shell,
    form_modal,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.pages.shared.file_upload import file_upload_zone
from durgam.states.auth import AuthState
from durgam.states.faculty_document import FacultyDocumentState


def _row_actions(record: dict) -> rx.Component:
    return rx.hstack(
        rx.button(
            "Edit",
            on_click=FacultyDocumentState.open_edit_by_id(record["id"]),
            size="1",
            variant="soft",
            cursor="pointer",
        ),
        rx.button(
            "Delete",
            on_click=FacultyDocumentState.open_delete_confirm_by_id(record["id"]),
            size="1",
            variant="soft",
            color_scheme="red",
            cursor="pointer",
        ),
        gap="0.4rem",
    )


def _doc_card(record: dict) -> rx.Component:
    return rx.box(
        rx.hstack(
            rx.vstack(
                rx.heading(record["document_type"], size="3"),
                rx.cond(
                    record["description"] != "",
                    rx.text(
                        record["description"],
                        font_size="0.85rem",
                        color="var(--color-muted)",
                    ),
                    rx.fragment(),
                ),
                rx.hstack(
                    rx.link(
                        record["file_name"],
                        href=record["download_url"],
                        is_external=True,
                        font_size="0.85rem",
                        color="var(--color-primary)",
                    ),
                    rx.text(
                        "· uploaded ",
                        record["uploaded_at_str"],
                        font_size="0.75rem",
                        color="var(--color-muted)",
                    ),
                    gap="0.5rem",
                    align="center",
                ),
                align="start",
                gap="0.25rem",
            ),
            rx.spacer(),
            _row_actions(record),
            width="100%",
            align="center",
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1rem",
        width="100%",
    )


def _doc_list() -> rx.Component:
    return rx.vstack(
        rx.foreach(FacultyDocumentState.documents, _doc_card),
        gap="0.75rem",
        width="100%",
    )


def _doc_form_modal() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading(
                rx.cond(
                    FacultyDocumentState.form_doc_id == "",
                    "Add Document",
                    "Edit Document",
                ),
                size="4",
                font_family="var(--font-sans)",
                margin_bottom="1rem",
            ),
            rx.form(
                rx.vstack(
                    rx.vstack(
                        rx.text(
                            "Document Type *",
                            font_size="0.85rem",
                            color="var(--color-muted)",
                        ),
                        rx.input(
                            name="form_document_type",
                            value=FacultyDocumentState.form_document_type,
                            on_change=FacultyDocumentState.set_form_document_type,
                            placeholder="e.g. PhD Certificate, Degree Certificate",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    rx.vstack(
                        rx.text("Description", font_size="0.85rem", color="var(--color-muted)"),
                        rx.text_area(
                            name="form_description",
                            value=FacultyDocumentState.form_description,
                            on_change=FacultyDocumentState.set_form_description,
                            placeholder="Optional note about this document",
                            width="100%",
                        ),
                        align="start",
                        gap="0.25rem",
                        width="100%",
                    ),
                    # File upload zone only in Add mode (file immutable on Edit).
                    rx.cond(
                        FacultyDocumentState.form_doc_id == "",
                        rx.vstack(
                            file_upload_zone(
                                on_drop=FacultyDocumentState.handle_document_upload(
                                    rx.upload_files()
                                ),
                                accept={"application/pdf": [".pdf"]},
                                label="Upload PDF (max 2MB)",
                            ),
                            rx.cond(
                                FacultyDocumentState.has_staged_file,
                                rx.text(
                                    "Selected: ",
                                    FacultyDocumentState.staged_file_name,
                                    font_size="0.8rem",
                                    color="var(--color-success-border)",
                                ),
                                rx.fragment(),
                            ),
                            align="start",
                            gap="0.25rem",
                            width="100%",
                        ),
                        rx.text(
                            "The uploaded file cannot be changed. To replace it, "
                            "delete this document and add a new one.",
                            font_size="0.75rem",
                            color="var(--color-muted)",
                        ),
                    ),
                    rx.hstack(
                        primary_btn("Save", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=FacultyDocumentState.cancel_form,
                            type="button",
                        ),
                        gap="0.75rem",
                        margin_top="0.5rem",
                    ),
                    gap="1rem",
                    width="100%",
                ),
                on_submit=FacultyDocumentState.save_document,
                reset_on_submit=False,
            ),
            gap="0",
            align="start",
            width="100%",
        ),
        is_open=FacultyDocumentState.show_form,
    )


def _delete_confirm_dialog() -> rx.Component:
    return confirmation_dialog(
        is_open=FacultyDocumentState.show_delete_confirm,
        title="Remove this document?",
        body=rx.vstack(
            rx.text("This will remove the following document. The file will also be deleted."),
            rx.text(
                FacultyDocumentState.deleting_type,
                font_weight="600",
            ),
            gap="0.4rem",
            align="start",
        ),
        on_confirm=FacultyDocumentState.confirm_delete,
        on_cancel=FacultyDocumentState.cancel_delete,
        confirm_label="Yes, delete",
        cancel_label="Cancel",
        danger=True,
    )


def _no_faculty_record_message() -> rx.Component:
    return rx.box(
        rx.heading("No Faculty Profile", size="5", margin_bottom="0.75rem"),
        rx.text(
            "You do not have a Faculty profile in this system. "
            "Contact the Registrar's office if this is an error.",
            color="var(--color-muted)",
            font_size="0.9rem",
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="2rem",
        width="100%",
    )


def faculty_documents_page() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        app_shell(
            rx.fragment(
                rx.toast.provider(),
                rx.vstack(
                    rx.hstack(
                        rx.heading("My Documents", size="6"),
                        rx.spacer(),
                        primary_btn(
                            "+ Add Document",
                            on_click=FacultyDocumentState.open_create_modal,
                        ),
                        width="100%",
                        align="center",
                        margin_bottom="0.5rem",
                    ),
                    rx.cond(
                        FacultyDocumentState.loading,
                        rx.center(rx.spinner(), padding="4rem"),
                        rx.cond(
                            ~FacultyDocumentState.has_faculty_record,
                            _no_faculty_record_message(),
                            rx.cond(
                                FacultyDocumentState.documents.length() == 0,
                                rx.box(
                                    rx.text(
                                        "No documents yet. Click '+ Add Document' to upload one.",
                                        color="var(--color-muted)",
                                        font_size="0.9rem",
                                    ),
                                    background="white",
                                    border="1px solid var(--color-rule)",
                                    border_radius="8px",
                                    padding="2rem",
                                    width="100%",
                                ),
                                _doc_list(),
                            ),
                        ),
                    ),
                    _doc_form_modal(),
                    _delete_confirm_dialog(),
                    spacing="4",
                    width="100%",
                ),
            ),
            container="lg",
        ),
        rx.fragment(),
    )
