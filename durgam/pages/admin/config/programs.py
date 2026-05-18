"""Program management page — /admin/config/programs (read-only with 6-tab detail)."""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer, typed_flash
from durgam.pages.shared.data_table import TableColumn, data_table
from durgam.states.config_program import AdminProgramsState


# ── helpers ───────────────────────────────────────────────────────────────────


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
                on_click=AdminProgramsState.open_detail(row["id"]),  # type: ignore[call-arg, func-returns-value]
            ),
        ),
    )


def _outcome_section(
    heading: str,
    rows: rx.Var,
) -> rx.Component:
    """Render one outcome section (PEOs / POs / PSOs)."""
    def make_row(item: rx.Var) -> rx.Component:
        return rx.hstack(
            rx.text(
                item["code"],  # type: ignore[index]
                font_weight="600",
                font_size="0.875rem",
                min_width="60px",
                color="var(--color-primary)",
            ),
            rx.text(
                item["description"],  # type: ignore[index]
                font_size="0.875rem",
            ),
            align="start",
            gap="1rem",
            padding="0.5rem 0",
            border_bottom="1px solid var(--color-rule)",
            width="100%",
        )

    return rx.vstack(
        rx.text(
            heading,
            font_weight="700",
            font_size="0.9rem",
            color="var(--color-muted)",
            text_transform="uppercase",
            letter_spacing="0.05em",
            margin_bottom="0.5rem",
        ),
        rx.cond(
            rows,
            rx.vstack(
                rx.foreach(rows, make_row),
                align="start",
                gap="0",
                width="100%",
            ),
            rx.text(
                "None recorded.",
                color="var(--color-muted)",
                font_size="0.875rem",
                font_style="italic",
            ),
        ),
        align="start",
        gap="0.25rem",
        width="100%",
        margin_bottom="1.5rem",
    )


def _tab_bar() -> rx.Component:
    tabs = [
        ("overview", "Overview"),
        ("outcomes", "Outcomes"),
        ("regulations", "Regulations"),
        ("scheme", "Scheme"),
        ("specialisations", "Specialisations"),
        ("exit_levels", "Exit Levels"),
    ]
    return rx.hstack(
        *[
            rx.button(
                label,
                on_click=AdminProgramsState.set_detail_active_tab(t),  # type: ignore[call-arg]
                background=rx.cond(
                    AdminProgramsState.detail_active_tab == t,
                    "var(--color-primary)",
                    "transparent",
                ),
                color=rx.cond(
                    AdminProgramsState.detail_active_tab == t,
                    "white",
                    "var(--color-muted)",
                ),
                border="1px solid var(--color-rule)",
                border_radius="6px",
                padding="0.4rem 0.8rem",
                font_size="0.85rem",
                cursor="pointer",
            )
            for t, label in tabs
        ],
        gap="0.5rem",
        flex_wrap="wrap",
        margin_bottom="1.5rem",
    )


def _field_row(label: str, value: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.text(
            label + ":",
            font_size="0.85rem",
            color="var(--color-muted)",
            min_width="130px",
            font_weight="500",
        ),
        rx.text(value, font_size="0.875rem"),
        align="start",
        gap="1rem",
        padding="0.4rem 0",
        border_bottom="1px solid var(--color-rule)",
        width="100%",
    )


def _tab_overview() -> rx.Component:
    return rx.vstack(
        rx.heading("Program Details", size="4", font_family="var(--font-sans)", margin_bottom="1rem"),
        _field_row("Code", AdminProgramsState.detail_code),
        _field_row("Name", AdminProgramsState.detail_name),
        _field_row("Degree Type", AdminProgramsState.detail_degree_type),
        _field_row("Duration (Years)", AdminProgramsState.detail_duration_years),
        align="start",
        gap="0",
        width="100%",
        max_width="600px",
    )


def _tab_outcomes() -> rx.Component:
    return rx.vstack(
        rx.heading("Program Outcomes", size="4", font_family="var(--font-sans)", margin_bottom="1rem"),
        _outcome_section("Program Educational Objectives (PEOs)", AdminProgramsState.detail_peos),
        _outcome_section("Program Outcomes (POs)", AdminProgramsState.detail_pos),
        _outcome_section("Program Specific Outcomes (PSOs)", AdminProgramsState.detail_psos),
        align="start",
        gap="0",
        width="100%",
    )


def _simple_table_two_col(
    rows: rx.Var,
    col1_key: str,
    col1_label: str,
    col2_key: str,
    col2_label: str,
) -> rx.Component:
    """Minimal two-column table for read-only sub-entity lists."""
    def make_row(item: rx.Var) -> rx.Component:
        return rx.table.row(
            rx.table.cell(rx.text(item[col1_key], font_size="0.875rem")),  # type: ignore[index]
            rx.table.cell(rx.text(item[col2_key], font_size="0.875rem")),  # type: ignore[index]
        )

    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell(
                    col1_label,
                    font_size="0.8rem",
                    font_weight="600",
                    color="var(--color-muted)",
                    text_transform="uppercase",
                    letter_spacing="0.04em",
                ),
                rx.table.column_header_cell(
                    col2_label,
                    font_size="0.8rem",
                    font_weight="600",
                    color="var(--color-muted)",
                    text_transform="uppercase",
                    letter_spacing="0.04em",
                ),
            )
        ),
        rx.table.body(rx.foreach(rows, make_row)),
        width="100%",
    )


def _simple_table_three_col(
    rows: rx.Var,
    col1_key: str,
    col1_label: str,
    col2_key: str,
    col2_label: str,
    col3_key: str,
    col3_label: str,
) -> rx.Component:
    """Minimal three-column table for read-only sub-entity lists."""
    def make_row(item: rx.Var) -> rx.Component:
        return rx.table.row(
            rx.table.cell(rx.text(item[col1_key], font_size="0.875rem")),  # type: ignore[index]
            rx.table.cell(rx.text(item[col2_key], font_size="0.875rem")),  # type: ignore[index]
            rx.table.cell(rx.text(item[col3_key], font_size="0.875rem")),  # type: ignore[index]
        )

    def make_header_cell(label: str) -> rx.Component:
        return rx.table.column_header_cell(
            label,
            font_size="0.8rem",
            font_weight="600",
            color="var(--color-muted)",
            text_transform="uppercase",
            letter_spacing="0.04em",
        )

    return rx.table.root(
        rx.table.header(
            rx.table.row(
                make_header_cell(col1_label),
                make_header_cell(col2_label),
                make_header_cell(col3_label),
            )
        ),
        rx.table.body(rx.foreach(rows, make_row)),
        width="100%",
    )


def _m13_note(text: str = "Rich management UI ships at M13.") -> rx.Component:
    return rx.text(
        text,
        color="var(--color-muted)",
        font_size="0.8rem",
        font_style="italic",
        margin_top="1rem",
    )


def _tab_regulations() -> rx.Component:
    return rx.vstack(
        rx.heading("Regulations", size="4", font_family="var(--font-sans)", margin_bottom="1rem"),
        rx.cond(
            AdminProgramsState.detail_regulations,
            _simple_table_three_col(
                AdminProgramsState.detail_regulations,
                "code", "Code",
                "effective_from_year", "Effective From",
                "description", "Description",
            ),
            rx.text("No regulations recorded.", color="var(--color-muted)", font_size="0.875rem", font_style="italic"),
        ),
        _m13_note("Rich management UI for Regulations ships at M13."),
        align="start",
        gap="0",
        width="100%",
    )


def _tab_scheme() -> rx.Component:
    def make_row(item: rx.Var) -> rx.Component:
        return rx.table.row(
            rx.table.cell(rx.text(item["semester"], font_size="0.875rem")),  # type: ignore[index]
            rx.table.cell(rx.text(item["total_credits"], font_size="0.875rem")),  # type: ignore[index]
            rx.table.cell(
                rx.text(
                    item["course_codes"],  # type: ignore[index]
                    font_size="0.8rem",
                    color="var(--color-muted)",
                )
            ),
        )

    def make_header_cell(label: str) -> rx.Component:
        return rx.table.column_header_cell(
            label,
            font_size="0.8rem",
            font_weight="600",
            color="var(--color-muted)",
            text_transform="uppercase",
            letter_spacing="0.04em",
        )

    return rx.vstack(
        rx.heading("Scheme of Instruction", size="4", font_family="var(--font-sans)", margin_bottom="1rem"),
        rx.cond(
            AdminProgramsState.detail_schemes,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        make_header_cell("Semester"),
                        make_header_cell("Total Credits"),
                        make_header_cell("Courses"),
                    )
                ),
                rx.table.body(rx.foreach(AdminProgramsState.detail_schemes, make_row)),
                width="100%",
            ),
            rx.text("No scheme entries recorded.", color="var(--color-muted)", font_size="0.875rem", font_style="italic"),
        ),
        _m13_note("Rich Scheme management UI ships at M13."),
        align="start",
        gap="0",
        width="100%",
    )


def _tab_specialisations() -> rx.Component:
    return rx.vstack(
        rx.heading("Specialisations", size="4", font_family="var(--font-sans)", margin_bottom="1rem"),
        rx.cond(
            AdminProgramsState.detail_specialisations,
            _simple_table_two_col(
                AdminProgramsState.detail_specialisations,
                "code", "Code",
                "name", "Name",
            ),
            rx.text("No specialisations recorded.", color="var(--color-muted)", font_size="0.875rem", font_style="italic"),
        ),
        _m13_note("Rich management UI ships at M13."),
        align="start",
        gap="0",
        width="100%",
    )


def _tab_exit_levels() -> rx.Component:
    return rx.vstack(
        rx.heading("Exit Levels", size="4", font_family="var(--font-sans)", margin_bottom="1rem"),
        rx.cond(
            AdminProgramsState.detail_exit_levels,
            _simple_table_two_col(
                AdminProgramsState.detail_exit_levels,
                "level_name", "Level",
                "required_credits", "Required Credits",
            ),
            rx.text("No exit levels recorded.", color="var(--color-muted)", font_size="0.875rem", font_style="italic"),
        ),
        _m13_note("Rich management UI ships at M13."),
        align="start",
        gap="0",
        width="100%",
    )


def _detail_view() -> rx.Component:
    return rx.box(
        # Back link
        rx.link(
            "← Programs",
            on_click=AdminProgramsState.close_detail,
            font_size="0.85rem",
            color="var(--color-primary)",
            font_family="var(--font-sans)",
            cursor="pointer",
            margin_bottom="1rem",
            display="block",
        ),
        # Header
        rx.vstack(
            rx.heading(
                AdminProgramsState.detail_code + " — " + AdminProgramsState.detail_name,
                size="5",
                font_family="var(--font-sans)",
            ),
            rx.text(
                AdminProgramsState.detail_degree_type + " · " + AdminProgramsState.detail_duration_years + " years",
                color="var(--color-muted)",
                font_size="0.9rem",
            ),
            align="start",
            gap="0.25rem",
            margin_bottom="1.5rem",
        ),
        # Tab bar
        _tab_bar(),
        # Tab panels — rx.cond-based switching
        rx.cond(
            AdminProgramsState.detail_active_tab == "overview",
            _tab_overview(),
            rx.cond(
                AdminProgramsState.detail_active_tab == "outcomes",
                _tab_outcomes(),
                rx.cond(
                    AdminProgramsState.detail_active_tab == "regulations",
                    _tab_regulations(),
                    rx.cond(
                        AdminProgramsState.detail_active_tab == "scheme",
                        _tab_scheme(),
                        rx.cond(
                            AdminProgramsState.detail_active_tab == "specialisations",
                            _tab_specialisations(),
                            _tab_exit_levels(),
                        ),
                    ),
                ),
            ),
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1.5rem",
        width="100%",
    )


def _list_view() -> rx.Component:
    return rx.vstack(
        rx.heading(
            "Programs",
            size="5",
            font_family="var(--font-sans)",
            margin_bottom="1.5rem",
        ),
        typed_flash(AdminProgramsState.flash, AdminProgramsState.flash_type),
        rx.cond(
            AdminProgramsState.loading,
            rx.center(rx.spinner(), padding="2rem"),
            data_table(
                rows=AdminProgramsState.programs,
                columns=[
                    TableColumn(key="code", label="Code"),
                    TableColumn(key="name", label="Name"),
                    TableColumn(key="degree_type", label="Degree Type"),
                    TableColumn(key="duration_years", label="Duration (Yrs)"),
                ],
                card_primary_key="name",
                is_mobile=False,
                actions=_kebab,
                empty_message="No programs found.",
            ),
        ),
        align="start",
        gap="0",
        width="100%",
    )


def admin_config_programs() -> rx.Component:
    return admin_page(
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.link(
                    "← Configuration",
                    href="/admin/config",
                    font_size="0.85rem",
                    color="var(--color-primary)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                    display="block",
                ),
                # Switch between list view and detail view
                rx.cond(
                    AdminProgramsState.show_detail,
                    _detail_view(),
                    _list_view(),
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
