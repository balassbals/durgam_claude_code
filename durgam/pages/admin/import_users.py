"""Admin bulk import page — /admin/import (two-stage CSV upload per §16)."""

import reflex as rx

from durgam.pages.components import nav_shell, page_footer
from durgam.states.admin_bulk_import import BulkImportState


def admin_import_users() -> rx.Component:
    def preview_row_component(row: dict) -> rx.Component:
        is_valid = row["status"].startswith("✓")
        return rx.hstack(
            rx.text(row["row"], width="3rem", font_size="0.8rem", color="var(--color-muted)"),
            rx.text(row["username"], width="140px", font_size="0.875rem"),
            rx.text(row["email"], width="220px", font_size="0.875rem"),
            rx.text(row["role_code"], width="120px", font_size="0.875rem"),
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

    return rx.vstack(
        nav_shell(),
        rx.box(
            rx.hstack(
                rx.link("← Admin", href="/admin", color="var(--color-primary)",
                        font_size="0.875rem"),
                rx.heading("Import Users", size="5", font_family="var(--font-sans)"),
                gap="1rem", align="center", margin_bottom="1.5rem",
            ),
            # Template download link
            rx.hstack(
                rx.text("Download template:", font_size="0.875rem"),
                rx.link(
                    "users_import_template.csv",
                    href="/admin/import/template.csv",
                    color="var(--color-primary)",
                    font_size="0.875rem",
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
                        # Reflex 0.9.2: on_drop (not on_upload); accept is MIME→[ext].
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
                                    border="1px solid var(--color-rule)",
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
                        rx.button(
                            rx.text("Commit ", BulkImportState.preview_valid.length(),
                                    " valid rows"),
                            on_click=BulkImportState.commit_import,
                            background="var(--color-primary)",
                            color="white",
                            border="none",
                            padding="0.5rem 1.25rem",
                            border_radius="4px",
                            cursor="pointer",
                            font_family="var(--font-sans)",
                        ),
                        rx.button(
                            "Start over",
                            on_click=BulkImportState.reset_import,
                            background="transparent",
                            border="1px solid var(--color-rule)",
                            padding="0.5rem 1.25rem",
                            border_radius="4px",
                            cursor="pointer",
                            font_family="var(--font-sans)",
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
                        " users imported successfully.",
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
                                    border="1px solid var(--color-rule)",
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
                        rx.link(
                            rx.button(
                                "View users",
                                background="var(--color-primary)",
                                color="white",
                                border="none",
                                padding="0.5rem 1.25rem",
                                border_radius="4px",
                                cursor="pointer",
                            ),
                            href="/admin/users",
                        ),
                        rx.button(
                            "Import more",
                            on_click=BulkImportState.reset_import,
                            background="transparent",
                            border="1px solid var(--color-rule)",
                            padding="0.5rem 1.25rem",
                            border_radius="4px",
                            cursor="pointer",
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
    )
