"""Reusable Faculty picker component (M10 Phase 11C).

A searchable dropdown that replaces the free-text employee_id input on the five
M5b assignment-style admin forms. Server-side search (≤50 rows) is performed by
the owning State via FacultyPickerService — Reflex State is the source of truth,
so the in-app picker uses the shared service through a state handler rather than
a client-side fetch (CLAUDE.md: no client-side app state).

Display format per row: ``<employee_id> — <title> <first_name> <last_name>``.

The component is render-only; all behaviour lives in the calling State. Pass:
  selected_label — Var[str], the chosen faculty's display ("" if none)
  search_value   — Var[str], the live search box value
  results        — Var[list[dict]], picker rows (each has "id" + "display")
  on_search      — handler(value: str) — server-side search
  on_select      — handler(faculty_id: str) — single-arg selection
  on_clear       — handler() — clear the current selection to re-search
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import secondary_btn


def _result_row(row: rx.Var, on_select) -> rx.Component:
    return rx.box(
        rx.text(row["display"], font_size="0.9rem"),
        on_click=lambda: on_select(row["id"]),
        cursor="pointer",
        padding="0.5rem 0.65rem",
        width="100%",
        border_radius="var(--radius-2)",
        _hover={"background": "var(--color-surface-2, #f1f1f4)"},
    )


def faculty_picker(
    *,
    selected_label: rx.Var,
    search_value: rx.Var,
    results: rx.Var,
    on_search,
    on_select,
    on_clear,
    placeholder: str = "Search faculty by name or employee ID",
) -> rx.Component:
    """Searchable faculty dropdown bound to the calling State's vars/handlers."""
    return rx.vstack(
        rx.text("Faculty *", font_size="0.85rem", color="var(--color-muted)"),
        rx.cond(
            selected_label != "",
            # Selected state — show the chosen faculty + a Change button.
            rx.hstack(
                rx.box(
                    rx.text(
                        selected_label,
                        font_size="0.9rem",
                        font_weight="500",
                    ),
                    padding="0.5rem 0.65rem",
                    border="1px solid var(--color-rule, #d8d8de)",
                    border_radius="var(--radius-2)",
                    background="var(--color-surface-2, #f6f6f8)",
                    flex="1",
                ),
                secondary_btn("Change", on_click=on_clear, type="button"),
                gap="0.5rem",
                align="center",
                width="100%",
            ),
            # Search state — input + live results list.
            rx.vstack(
                rx.input(
                    value=search_value,
                    on_change=on_search,
                    placeholder=placeholder,
                    width="100%",
                ),
                rx.cond(
                    results.length() > 0,
                    rx.vstack(
                        rx.foreach(
                            results,
                            lambda row: _result_row(row, on_select),
                        ),
                        gap="0.1rem",
                        width="100%",
                        max_height="14rem",
                        overflow_y="auto",
                        border="1px solid var(--color-rule, #d8d8de)",
                        border_radius="var(--radius-2)",
                        padding="0.25rem",
                    ),
                    rx.cond(
                        search_value != "",
                        rx.text(
                            "No matching faculty.",
                            font_size="0.8rem",
                            color="var(--color-muted)",
                            padding="0.25rem 0.1rem",
                        ),
                        rx.fragment(),
                    ),
                ),
                gap="0.35rem",
                align="start",
                width="100%",
            ),
        ),
        align="start",
        gap="0.25rem",
        width="100%",
    )
