"""Reusable file-upload drop zone component."""

import reflex as rx


def file_upload_zone(
    on_drop: rx.EventHandler,
    *,
    accept: dict[str, list[str]] | None = None,
    label: str = "Drag & drop a file here, or click to browse",
) -> rx.Component:
    """Styled upload zone wrapping rx.upload."""
    return rx.upload(
        rx.box(
            rx.text(
                label,
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
        accept=accept or {},
        on_drop=on_drop,
    )
