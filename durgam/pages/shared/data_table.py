"""Responsive data table component (two-tier table pattern, M2).

Tier 1 — Card layout (≤4 key columns, lookup/management lists):
  Used for user list, role list, permission list. Below 768px, each row
  becomes a stacked card. Above 768px, normal table.

Tier 2 — Horizontal scroll with sticky first column (5+ comparison columns):
  NOT this component. Use rx.table with `overflow_x="auto"` directly for
  course allocation, attendance, exam results, leave requests, audit log.
  See CLAUDE.md "Patterns established at M2".

Usage (Tier 1):
    data_table(
        rows=[{"username": "jdoe", "email": "...", "_id": "uuid"}],
        columns=[
            TableColumn(key="username", label="Username"),
            TableColumn(key="email", label="Email"),
        ],
        card_primary_key="username",
        is_mobile=SomeState.is_mobile,
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
    rows: list[dict],
    columns: list[TableColumn],
    card_primary_key: str,
    is_mobile: bool,
    actions: Callable[[dict], rx.Component] | None = None,
    empty_message: str = "No records found.",
    loading: bool = False,
) -> rx.Component:
    """Render rows as a responsive table (desktop) or card stack (mobile).

    is_mobile is a Reflex state var — the component renders both views and
    uses rx.cond to switch between them at runtime.
    """
    if loading:
        return _loading_skeleton(len(columns))

    if not rows:
        return _empty_state(empty_message)

    return rx.cond(
        is_mobile,
        _card_stack(rows, columns, card_primary_key, actions),
        _table_view(rows, columns, actions),
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


def _table_view(
    rows: list[dict],
    columns: list[TableColumn],
    actions: Callable[[dict], rx.Component] | None,
) -> rx.Component:
    visible_cols = [c for c in columns if not c.hidden_on_card or True]  # all cols in table mode

    header_cells = [
        rx.table.column_header_cell(
            col.label,
            font_weight="600",
            font_size="0.8rem",
            color="var(--color-muted)",
            text_transform="uppercase",
            letter_spacing="0.04em",
        )
        for col in visible_cols
    ]
    if actions:
        header_cells.append(
            rx.table.column_header_cell("", width="3rem")
        )

    table_rows = []
    for row in rows:
        cells = [
            rx.table.cell(
                rx.text(str(row.get(col.key, "")), font_size="0.875rem"),
            )
            for col in visible_cols
        ]
        if actions:
            cells.append(rx.table.cell(actions(row)))
        table_rows.append(rx.table.row(*cells))

    return rx.table.root(
        rx.table.header(rx.table.row(*header_cells)),
        rx.table.body(*table_rows),
        width="100%",
    )


def _card_stack(
    rows: list[dict],
    columns: list[TableColumn],
    primary_key: str,
    actions: Callable[[dict], rx.Component] | None,
) -> rx.Component:
    cards = []
    visible_cols = [c for c in columns if not c.hidden_on_card]

    for row in rows:
        primary_val = str(row.get(primary_key, ""))
        secondary_items = []
        for col in visible_cols:
            if col.key == primary_key:
                continue
            secondary_items.append(
                rx.hstack(
                    rx.text(col.label + ":", font_size="0.75rem", color="var(--color-muted)",
                            min_width="90px"),
                    rx.text(str(row.get(col.key, "")), font_size="0.875rem"),
                    align="start",
                    gap="0.5rem",
                )
            )

        card_content = [
            rx.hstack(
                rx.text(primary_val, font_weight="600", font_size="0.9rem"),
                rx.spacer(),
                *([] if actions is None else [actions(row)]),
                align="center",
                width="100%",
            ),
            *secondary_items,
        ]

        cards.append(
            rx.box(
                *card_content,
                border="1px solid var(--color-rule)",
                border_radius="6px",
                padding="0.75rem 1rem",
                background="white",
                margin_bottom="0.5rem",
            )
        )

    return rx.box(*cards, width="100%")
