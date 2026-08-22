"""Admin faculty bulk import page — /admin/faculty/import (M10 Phase 12)."""

import reflex as rx

from durgam.pages.components import admin_page, app_shell, primary_btn, secondary_btn
from durgam.states.faculty_bulk_import import FacultyBulkImportState


def _preview_header() -> rx.Component:
    return rx.hstack(
        rx.text(
            "#", width="3rem", font_size="0.75rem", font_weight="600", color="var(--color-muted)"
        ),
        rx.text(
            "Employee ID",
            width="160px",
            font_size="0.75rem",
            font_weight="600",
            color="var(--color-muted)",
        ),
        rx.text(
            "Username",
            width="160px",
            font_size="0.75rem",
            font_weight="600",
            color="var(--color-muted)",
        ),
        rx.text(
            "Name",
            width="180px",
            font_size="0.75rem",
            font_weight="600",
            color="var(--color-muted)",
        ),
        rx.text(
            "Status", font_size="0.75rem", font_weight="600", color="var(--color-muted)", flex="1"
        ),
        padding="0.4rem 0",
        border_bottom="2px solid var(--color-rule)",
    )


def _preview_row(row: dict) -> rx.Component:
    is_valid = row["status"].startswith("✓")
    return rx.hstack(
        rx.text(row["row"], width="3rem", font_size="0.8rem", color="var(--color-muted)"),
        rx.text(row["col1"], width="160px", font_size="0.875rem"),
        rx.text(row["col2"], width="160px", font_size="0.875rem"),
        rx.text(row["col3"], width="180px", font_size="0.875rem"),
        rx.text(
            row["status"],
            font_size="0.8rem",
            color=rx.cond(
                is_valid, "var(--color-success, #27ae60)", "var(--color-danger, #c0392b)"
            ),
            flex="1",
        ),
        padding="0.4rem 0",
        border_bottom="1px solid var(--color-rule)",
        align="start",
    )


def admin_faculty_import_page() -> rx.Component:
    return admin_page(
        app_shell(
            rx.vstack(
                rx.hstack(
                    rx.link(
                        "← Admin", href="/admin", color="var(--color-primary)", font_size="0.875rem"
                    ),
                    rx.link(
                        "/ Faculty",
                        href="/admin/faculty",
                        color="var(--color-primary)",
                        font_size="0.875rem",
                    ),
                    rx.heading("/ Faculty Import", size="5", font_family="var(--font-sans)"),
                    gap="0.5rem",
                    align="center",
                    margin_bottom="1.5rem",
                ),
                # Template download
                rx.hstack(
                    rx.text("Download template:", font_size="0.875rem"),
                    rx.button(
                        "import_faculty_template.csv",
                        on_click=FacultyBulkImportState.download_template,
                        background="transparent",
                        border="none",
                        color="var(--color-primary)",
                        font_size="0.875rem",
                        cursor="pointer",
                        padding="0",
                        text_decoration="underline",
                    ),
                    margin_bottom="1.5rem",
                    gap="0.5rem",
                    align="center",
                ),
                # Required columns info
                rx.box(
                    rx.text(
                        "Required columns: employee_id, username, first_name, last_name, "
                        "designation_code, dept_code, campus_code, joining_date (YYYY-MM-DD), "
                        "gender (M/F/O). "
                        "If a username does not exist, include an 'email' column and a new "
                        "account will be created automatically (must_change_password=True).",
                        font_size="0.8rem",
                        color="var(--color-muted)",
                    ),
                    background="var(--color-surface, #faf9f7)",
                    border="1px solid var(--color-rule)",
                    border_radius="4px",
                    padding="0.75rem 1rem",
                    margin_bottom="1.5rem",
                ),
                # Flash
                rx.cond(
                    FacultyBulkImportState.flash != "",
                    rx.box(
                        rx.text(FacultyBulkImportState.flash, font_size="0.875rem"),
                        background="var(--color-surface, #faf9f7)",
                        border="1px solid var(--color-rule)",
                        border_radius="4px",
                        padding="0.75rem 1rem",
                        margin_bottom="1rem",
                    ),
                    rx.fragment(),
                ),
                # Stage 1: upload
                rx.cond(
                    ~FacultyBulkImportState.preview_ready & ~FacultyBulkImportState.import_complete,
                    rx.box(
                        rx.heading("Step 1: Upload CSV", size="3", margin_bottom="0.75rem"),
                        rx.upload(
                            rx.box(
                                rx.text(
                                    "Drag & drop a CSV file here, or click to browse",
                                    color="var(--color-muted)",
                                    font_size="0.875rem",
                                    text_align="center",
                                ),
                                border="2px dashed var(--color-rule)",
                                border_radius="6px",
                                padding="2rem",
                                cursor="pointer",
                                _hover={"border_color": "var(--color-primary)"},
                            ),
                            accept={"text/csv": [".csv"]},
                            on_drop=FacultyBulkImportState.upload_csv,
                        ),
                        margin_bottom="1rem",
                    ),
                    rx.fragment(),
                ),
                # Stage 2: preview
                rx.cond(
                    FacultyBulkImportState.preview_ready,
                    rx.box(
                        rx.heading("Step 2: Review", size="3", margin_bottom="0.75rem"),
                        rx.hstack(
                            rx.text(
                                FacultyBulkImportState.preview_valid.length(),
                                " valid, ",
                                FacultyBulkImportState.preview_invalid.length(),
                                " invalid",
                                font_size="0.875rem",
                            ),
                            rx.spacer(),
                            rx.cond(
                                FacultyBulkImportState.error_report_csv != "",
                                rx.link(
                                    rx.button(
                                        "Download error report",
                                        background="transparent",
                                        color="var(--color-primary)",
                                        border="1px solid var(--color-primary)",
                                        padding="0.3rem 0.75rem",
                                        border_radius="4px",
                                        cursor="pointer",
                                        font_size="0.8rem",
                                    ),
                                    download="faculty_import_errors.csv",
                                ),
                                rx.fragment(),
                            ),
                            align="center",
                            width="100%",
                            margin_bottom="0.5rem",
                        ),
                        rx.box(
                            _preview_header(),
                            rx.foreach(FacultyBulkImportState.preview_valid, _preview_row),
                            rx.foreach(FacultyBulkImportState.preview_invalid, _preview_row),
                            border="1px solid var(--color-rule)",
                            border_radius="6px",
                            padding="0.5rem 1rem",
                            background="white",
                            max_height="400px",
                            overflow_y="auto",
                            margin_bottom="1rem",
                        ),
                        rx.cond(
                            FacultyBulkImportState.preview_valid.length() > 0,
                            rx.hstack(
                                primary_btn(
                                    rx.text(
                                        "Commit ",
                                        FacultyBulkImportState.preview_valid.length(),
                                        " valid rows",
                                    ),
                                    on_click=FacultyBulkImportState.commit_import,
                                ),
                                secondary_btn(
                                    "Start over",
                                    on_click=FacultyBulkImportState.reset_import,
                                ),
                                gap="1rem",
                            ),
                            secondary_btn(
                                "Start over",
                                on_click=FacultyBulkImportState.reset_import,
                            ),
                        ),
                    ),
                    rx.fragment(),
                ),
                # Stage 3: result
                rx.cond(
                    FacultyBulkImportState.import_complete,
                    rx.box(
                        rx.heading("Import Complete", size="3", margin_bottom="0.75rem"),
                        rx.text(
                            FacultyBulkImportState.import_success_count,
                            " faculty records imported successfully.",
                            font_size="0.875rem",
                            margin_bottom="0.5rem",
                        ),
                        rx.cond(
                            FacultyBulkImportState.error_report_csv != "",
                            rx.hstack(
                                rx.text(
                                    FacultyBulkImportState.late_errors.length(),
                                    " rows failed at commit time.",
                                    font_size="0.875rem",
                                    color="var(--color-danger, #c0392b)",
                                ),
                                rx.link(
                                    rx.button(
                                        "Download error report",
                                        background="transparent",
                                        color="var(--color-primary)",
                                        border="1px solid var(--color-primary)",
                                        padding="0.3rem 0.75rem",
                                        border_radius="4px",
                                        cursor="pointer",
                                        font_size="0.8rem",
                                    ),
                                    download="faculty_import_errors.csv",
                                ),
                                gap="1rem",
                                align="center",
                            ),
                            rx.fragment(),
                        ),
                        rx.hstack(
                            secondary_btn(
                                "Import more",
                                on_click=FacultyBulkImportState.reset_import,
                            ),
                            gap="1rem",
                            margin_top="1rem",
                        ),
                    ),
                    rx.fragment(),
                ),
                align="start",
                width="100%",
            ),
            container="md",
        )
    )
