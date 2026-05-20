"""Department detail — read-only (/about/departments/[dept_code])."""

import reflex as rx

from durgam.pages.components import nav_shell, page_footer
from durgam.states.about import AboutDeptDetailState
from durgam.states.auth import AuthState


def _mission_item(m: dict) -> rx.Component:
    return rx.hstack(
        rx.text(
            "•",
            color="var(--color-primary)",
            font_size="1.1rem",
            flex_shrink="0",
            margin_top="0.05rem",
        ),
        rx.text(
            m["statement"],
            font_family="var(--font-sans)",
            font_size="0.95rem",
            line_height="1.65",
            color="var(--color-body)",
        ),
        align="start",
        gap="0.6rem",
        width="100%",
    )


def about_dept_detail() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.link(
                    "← All Departments",
                    href="/about/departments",
                    font_size="0.85rem",
                    color="var(--color-primary)",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                    display="block",
                ),
                rx.heading(
                    AboutDeptDetailState.dept_name,
                    size="5",
                    font_family="var(--font-sans)",
                    margin_bottom="1.5rem",
                ),
                rx.cond(
                    AboutDeptDetailState.loading,
                    rx.center(rx.spinner(), padding="2rem"),
                    rx.cond(
                        AboutDeptDetailState.not_found,
                        rx.text(
                            "Department not found.",
                            color="var(--color-muted)",
                            font_family="var(--font-sans)",
                        ),
                        rx.cond(
                            AboutDeptDetailState.no_vm,
                            rx.box(
                                rx.text(
                                    "Vision and mission for this department have not been configured yet.",
                                    color="var(--color-muted)",
                                    font_family="var(--font-sans)",
                                    font_size="0.95rem",
                                ),
                                padding="1.5rem",
                                border="1px dashed var(--color-rule)",
                                border_radius="6px",
                                background="white",
                            ),
                            rx.vstack(
                                rx.vstack(
                                    rx.text(
                                        "Vision",
                                        font_weight="700",
                                        font_size="1rem",
                                        color="var(--color-primary)",
                                        font_family="var(--font-sans)",
                                    ),
                                    rx.text(
                                        AboutDeptDetailState.dept_vision,
                                        font_family="var(--font-sans)",
                                        font_size="0.95rem",
                                        line_height="1.65",
                                        color="var(--color-body)",
                                    ),
                                    align="start",
                                    gap="0.5rem",
                                    width="100%",
                                    padding="1.25rem",
                                    background="white",
                                    border="1px solid var(--color-rule)",
                                    border_radius="6px",
                                ),
                                rx.cond(
                                    AboutDeptDetailState.dept_missions.length() > 0,  # type: ignore[attr-defined]
                                    rx.vstack(
                                        rx.text(
                                            "Mission",
                                            font_weight="700",
                                            font_size="1rem",
                                            color="var(--color-primary)",
                                            font_family="var(--font-sans)",
                                        ),
                                        rx.vstack(
                                            rx.foreach(
                                                AboutDeptDetailState.dept_missions,
                                                _mission_item,
                                            ),
                                            align="start",
                                            gap="0.6rem",
                                            width="100%",
                                        ),
                                        align="start",
                                        gap="0.75rem",
                                        width="100%",
                                        padding="1.25rem",
                                        background="white",
                                        border="1px solid var(--color-rule)",
                                        border_radius="6px",
                                    ),
                                    rx.fragment(),
                                ),
                                align="start",
                                gap="1rem",
                                width="100%",
                            ),
                        ),
                    ),
                ),
                padding="2rem",
                max_width="800px",
                width="100%",
            ),
            page_footer(),
            align="start",
            width="100%",
            min_height="100vh",
            background="var(--color-background, #f5f0eb)",
        ),
        rx.fragment(),
    )
