"""Admin bulk import page — /admin/import (two-stage CSV upload per §16).

Supports users, courses, and programs. Faculty/student import deferred to
M10/M12 (models don't exist yet).
"""

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer, primary_btn, secondary_btn
from durgam.states.admin_bulk_import import BulkImportState


def _type_button(label: str, value: str) -> rx.Component:
    is_active = BulkImportState.import_type == value
    return rx.button(
        label,
        on_click=BulkImportState.set_import_type(value),
        background=rx.cond(is_active, "var(--color-primary)", "transparent"),
        color=rx.cond(is_active, "white", "var(--color-primary)"),
        border=f"1px solid var(--color-primary)",
        border_radius="4px",
        padding="0.4rem 1rem",
        cursor="pointer",
        font_family="var(--font-sans)",
        font_size="0.875rem",
    )


def admin_import_users() -> rx.Component:
    def preview_row_component(row: dict) -> rx.Component:
        is_valid = row["status"].startswith("✓")
        return rx.hstack(
            rx.text(row["row"], width="3rem", font_size="0.8rem", color="var(--color-muted)"),
            rx.text(row["col1"], width="140px", font_size="0.875rem"),
            rx.text(row["col2"], width="220px", font_size="0.875rem"),
            rx.text(row["col3"], width="120px", font_size="0.875rem"),
            rx.text(
                row["status"],
                font_size="0.8rem",
                color=rx.cond(is_valid, "var(--color-success, #27ae60)",
                               "var(--color-danger, #c0392b)"),
                flex="1",
            ),
            padding="0.4rem 0",
            border_bottom="1px solid var(--color-rule)",
            align="start",
        )

    def preview_header() -> rx.Component:
        return rx.hstack(
            rx.text("#", width="3rem", font_size="0.75rem", font_weight="600",
                    color="var(--color-muted)"),
            rx.text(BulkImportState.col1_header, width="140px", font_size="0.75rem",
                    font_weight="600"),
            rx.text(BulkImportState.col2_header, width="220px", font_size="0.75rem",
                    font_weight="600"),
            rx.text(BulkImportState.col3_header, width="120px", font_size="0.75rem",
                    font_weight="600"),
            rx.text("Status", font_size="0.75rem", font_weight="600", flex="1"),
            padding="0.4rem 0",
            border_bottom="2px solid var(--color-rule)",
        )

    entity_label = rx.cond(
        BulkImportState.import_type == "courses",
        "courses",
        rx.cond(
            BulkImportState.import_type == "programs",
            "programs",
            "users",
        ),
    )

    template_name = rx.cond(
        BulkImportState.import_type == "courses",
        "import_course_template.csv",
        rx.cond(
            BulkImportState.import_type == "programs",
            "import_program_template.csv",
            "import_user_template.csv",
        ),
    )

    return admin_page(rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link("← Admin", href="/admin", color="var(--color-primary)",
                        font_size="0.875rem"),
                rx.heading("Bulk Import", size="5", font_family="var(--font-sans)"),
                gap="1rem", align="center", margin_bottom="1rem",
            ),
            # Import type selector — only show tabs the user has permission for
            rx.hstack(
                rx.cond(
                    BulkImportState.can_import_users,
                    _type_button("Users", "users"),
                    rx.fragment(),
                ),
                rx.cond(
                    BulkImportState.can_import_courses,
                    _type_button("Courses", "courses"),
                    rx.fragment(),
                ),
                rx.cond(
                    BulkImportState.can_import_programs,
                    _type_button("Programs", "programs"),
                    rx.fragment(),
                ),
                gap="0.5rem",
                margin_bottom="1.5rem",
            ),
            # Template download
            rx.hstack(
                rx.text("Download template:", font_size="0.875rem"),
                rx.button(
                    template_name,
                    on_click=BulkImportState.download_template,
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
            rx.cond(
                BulkImportState.flash != "",
                rx.box(
                    rx.text(BulkImportState.flash, font_size="0.875rem"),
                    background="var(--color-surface, #faf9f7)",
                    border="1px solid var(--color-rule)", border_radius="4px",
                    padding="0.75rem 1rem", margin_bottom="1rem",
                ),
                rx.fragment(),
            ),
            # Stage 1: upload
            rx.cond(
                ~BulkImportState.preview_ready & ~BulkImportState.import_complete,
                rx.box(
                    rx.heading("Step 1: Upload CSV", size="3", margin_bottom="0.75rem"),
                    rx.upload(
                        rx.box(
                            rx.text("Drag & drop a CSV file here, or click to browse",
                                    color="var(--color-muted)", font_size="0.875rem",
                                    text_align="center"),
                            border="2px dashed var(--color-rule)",
                            border_radius="6px",
                            padding="2rem",
                            cursor="pointer",
                            _hover={"border_color": "var(--color-primary)"},
                        ),
                        accept={"text/csv": [".csv"]},
                        on_drop=BulkImportState.upload_csv,
                    ),
                    margin_bottom="1rem",
                ),
                rx.fragment(),
            ),
            # Stage 2: preview
            rx.cond(
                BulkImportState.preview_ready,
                rx.box(
                    rx.heading("Step 2: Review", size="3", margin_bottom="0.75rem"),
                    rx.hstack(
                        rx.text(
                            BulkImportState.preview_valid.length(),
                            " valid, ",
                            BulkImportState.preview_invalid.length(),
                            " invalid",
                            font_size="0.875rem",
                        ),
                        rx.spacer(),
                        rx.cond(
                            BulkImportState.error_report_csv != "",
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
                                download="import_errors.csv",
                            ),
                            rx.fragment(),
                        ),
                        align="center",
                        width="100%",
                        margin_bottom="0.5rem",
                    ),
                    rx.box(
                        preview_header(),
                        rx.foreach(BulkImportState.preview_valid, preview_row_component),
                        rx.foreach(BulkImportState.preview_invalid, preview_row_component),
                        border="1px solid var(--color-rule)",
                        border_radius="6px",
                        padding="0.5rem 1rem",
                        background="white",
                        max_height="400px",
                        overflow_y="auto",
                        margin_bottom="1rem",
                    ),
                    rx.hstack(
                        primary_btn(
                            rx.text("Commit ", BulkImportState.preview_valid.length(),
                                    " valid rows"),
                            on_click=BulkImportState.commit_import,
                        ),
                        secondary_btn(
                            "Start over",
                            on_click=BulkImportState.reset_import,
                        ),
                        gap="1rem",
                    ),
                ),
                rx.fragment(),
            ),
            # Stage 3: result
            rx.cond(
                BulkImportState.import_complete,
                rx.box(
                    rx.heading("Import Complete", size="3", margin_bottom="0.75rem"),
                    rx.text(
                        BulkImportState.import_success_count,
                        " ", entity_label, " imported successfully.",
                        font_size="0.875rem",
                        margin_bottom="0.5rem",
                    ),
                    rx.cond(
                        BulkImportState.error_report_csv != "",
                        rx.hstack(
                            rx.text(
                                BulkImportState.late_errors.length(),
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
                                download="import_errors.csv",
                            ),
                            gap="1rem",
                            align="center",
                        ),
                        rx.fragment(),
                    ),
                    rx.hstack(
                        secondary_btn(
                            "Import more",
                            on_click=BulkImportState.reset_import,
                        ),
                        gap="1rem",
                        margin_top="1rem",
                    ),
                ),
                rx.fragment(),
            ),
            padding="2rem",
            max_width="900px",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
        min_height="100vh",
        background="var(--color-background, #f5f0eb)",
    ))
