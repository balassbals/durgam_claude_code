"""Reusable file-upload drop zone component."""

import reflex as rx


def file_upload_zone(
    on_drop: rx.EventHandler | None = None,
    *,
    upload_id: str | None = None,
    accept: dict[str, list[str]] | None = None,
    label: str = "Drag & drop a file here, or click to browse",
) -> rx.Component:
    """Styled upload zone wrapping rx.upload.

    Two modes:
    - **Immediate** (on_drop provided): fires handler on file drop.
    - **Staged** (upload_id provided, no on_drop): files are selected
      client-side; caller triggers upload via
      ``rx.upload_files(upload=upload_id)`` on a Submit button.
    """
    kwargs: dict = {"accept": accept or {}}
    if upload_id:
        kwargs["id"] = upload_id
    if on_drop:
        kwargs["on_drop"] = on_drop
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
        **kwargs,
    )
