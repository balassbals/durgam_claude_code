"""Responsive data table component (two-tier table pattern, M2).

Works with Reflex state vars (Var[list[dict]]) by using rx.foreach for
row iteration and rx.cond for empty-state detection. Python for-loops and
`if not rows` are not used because Reflex vars cannot be converted to bool
in Python at component build time.

Tier 1 — Card layout (≤4 key columns, lookup/management lists):
  Used for user list, role list, permission list. Below 768px (is_mobile=True),
  each row becomes a stacked card. Above 768px, normal table. Pass
  is_mobile=False to always show the table (acceptable for desktop-first pages).

Tier 2 — Horizontal scroll with sticky first column (5+ comparison columns):
  NOT this component. Use rx.table directly with overflow_x="auto".
  See CLAUDE.md "Patterns established at M2".

Usage:
    data_table(
        rows=AdminUsersState.users,  # Var[list[dict]]
        columns=[
            TableColumn(key="username", label="Username"),
            TableColumn(key="email", label="Email"),
        ],
        card_primary_key="username",
        is_mobile=False,
        actions=lambda row: kebab_menu(row),
    )
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import reflex as rx


@dataclass
class TableColumn:
    key: str
    label: str
    hidden_on_card: bool = False  # if True, only shown in table mode


def data_table(
    *,
    rows: list | rx.Var,
    columns: list[TableColumn],
    card_primary_key: str,
    is_mobile: bool | rx.Var,
    actions: Callable | None = None,
    empty_message: str = "No records found.",
    loading: bool = False,
) -> rx.Component:
    """Render rows as a responsive table (desktop) or card stack (mobile).

    rows can be a Reflex state var (Var[list[dict]]) — rx.foreach handles
    reactive iteration. columns is always a Python list (build-time known).
    """
    if loading:
        return _loading_skeleton(len(columns))

    # Build the table and card views using rx.foreach for reactive rendering.
    table_view = _reactive_table_view(rows, columns, actions)
    card_view = _reactive_card_stack(rows, columns, card_primary_key, actions)

    content = rx.cond(
        is_mobile,
        card_view,
        table_view,
    )

    # Show empty state when rows is falsy (empty list in Reflex).
    return rx.cond(
        rows,
        content,
        _empty_state(empty_message),
    )


def _loading_skeleton(col_count: int) -> rx.Component:
    return rx.box(
        *[
            rx.box(
                background="var(--color-rule)",
                height="2rem",
                border_radius="4px",
                margin_bottom="0.5rem",
                opacity="0.5",
            )
            for _ in range(5)
        ],
        width="100%",
        padding="1rem",
    )


def _empty_state(message: str) -> rx.Component:
    return rx.box(
        rx.text(message, color="var(--color-muted)", font_size="0.9rem"),
        padding="2rem",
        text_align="center",
        width="100%",
    )


def _reactive_table_view(
    rows: list | rx.Var,
    columns: list[TableColumn],
    actions: Callable | None,
) -> rx.Component:
    """Table view using rx.foreach for reactive row rendering."""
    header_cells = [
        rx.table.column_header_cell(
            col.label,
            font_weight="600",
            font_size="0.8rem",
            color="var(--color-muted)",
            text_transform="uppercase",
            letter_spacing="0.04em",
        )
        for col in columns
    ]
    if actions is not None:
        header_cells.append(rx.table.column_header_cell("", width="3rem"))

    # The row-builder must close over the Python-level columns list and
    # actions callable. rx.foreach calls it with each Var[dict] item.
    def make_row(row: rx.Var) -> rx.Component:
        cells = [
            rx.table.cell(rx.text(row[col.key], font_size="0.875rem"))  # type: ignore[index]
            for col in columns
        ]
        if actions is not None:
            cells.append(rx.table.cell(actions(row)))
        return rx.table.row(*cells)

    return rx.table.root(
        rx.table.header(rx.table.row(*header_cells)),
        rx.table.body(rx.foreach(rows, make_row)),
        width="100%",
    )


def _reactive_card_stack(
    rows: list | rx.Var,
    columns: list[TableColumn],
    card_primary_key: str,
    actions: Callable | None,
) -> rx.Component:
    """Card stack using rx.foreach for reactive rendering."""
    card_cols = [c for c in columns if not c.hidden_on_card]

    def make_card(row: rx.Var) -> rx.Component:
        secondary_items = [
            rx.hstack(
                rx.text(
                    col.label + ":",
                    font_size="0.75rem",
                    color="var(--color-muted)",
                    min_width="90px",
                ),
                rx.text(row[col.key], font_size="0.875rem"),  # type: ignore[index]  # noqa
                align="start",
                gap="0.5rem",
            )
            for col in card_cols
            if col.key != card_primary_key
        ]

        action_part = ([actions(row)] if actions is not None else [])

        return rx.box(
            rx.hstack(
                rx.text(row[card_primary_key], font_weight="600", font_size="0.9rem"),  # type: ignore[index]
                rx.spacer(),
                *action_part,
                align="center",
                width="100%",
            ),
            *secondary_items,
            border="1px solid var(--color-rule)",
            border_radius="6px",
            padding="0.75rem 1rem",
            background="white",
            margin_bottom="0.5rem",
        )

    return rx.box(rx.foreach(rows, make_card), width="100%")
