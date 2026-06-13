"""Announcements page — browse, compose, and detail (M9 Phase 6b/8b)."""

import reflex as rx

from durgam.api import DOWNLOAD_PREFIX
from durgam.pages.components import (
    config_toast,
    destructive_btn,
    form_modal,
    nav_shell,
    page_footer,
    primary_btn,
    secondary_btn,
)
from durgam.pages.shared.file_upload import file_upload_zone
from durgam.states.announcements import (
    AnnouncementBrowseState,
    AnnouncementComposerState,
    AnnouncementDetailState,
)
from durgam.states.auth import AuthState

_TAB_OPTIONS = [
    {"value": "received", "label": "Received"},
    {"value": "sent", "label": "Sent (My Announcements)"},
]

_IMPORTANCE_OPTIONS = [
    {"value": "all", "label": "All"},
    {"value": "very_important", "label": "Very Important"},
    {"value": "normal", "label": "Normal"},
]


def _importance_badge(row: rx.Var) -> rx.Component:
    return rx.match(
        row["importance"],
        ("very_important", rx.badge("Very Important", color_scheme="red")),
        rx.badge("Normal", color_scheme="gray"),
    )


def _withdrawn_badge(row: rx.Var) -> rx.Component:
    return rx.cond(
        row["is_withdrawn"],
        rx.badge("Withdrawn", color_scheme="gray", variant="outline"),
        rx.fragment(),
    )


def _row_card(row: rx.Var) -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                _importance_badge(row),
                rx.badge(row["category_code"], color_scheme="indigo", variant="soft"),
                _withdrawn_badge(row),
                rx.spacer(),
                rx.text(
                    row["scheduled_at"],
                    font_size="0.78rem",
                    color="var(--color-muted)",
                ),
                align="center",
                width="100%",
                gap="0.5rem",
                flex_wrap="wrap",
            ),
            rx.text(
                row["title"],
                font_weight="600",
                font_size="1rem",
                font_family="var(--font-sans)",
                color="var(--color-text-primary)",
            ),
            rx.text(
                row["snippet"],
                font_size="0.875rem",
                color="var(--color-muted)",
                line_clamp="2",
            ),
            rx.hstack(
                rx.text(
                    rx.icon("user", size=13),
                    " ",
                    row["composer_role_code"],
                    font_size="0.78rem",
                    color="var(--color-muted)",
                ),
                rx.spacer(),
                secondary_btn(
                    rx.icon("eye", size=13),
                    " View",
                    on_click=AnnouncementDetailState.open_detail(row["id"]),
                    size="1",
                ),
                align="center",
                width="100%",
            ),
            gap="0.5rem",
            align="start",
            width="100%",
        ),
        padding="1rem",
        border="1px solid var(--color-rule)",
        border_radius="var(--radius-2)",
        background="var(--color-surface)",
        width="100%",
        _hover={"border_color": "var(--color-primary)"},
        cursor="default",
    )


def _filter_strip() -> rx.Component:
    return rx.hstack(
        # Tab selector
        rx.select.root(
            rx.select.trigger(placeholder="Tab"),
            rx.select.content(
                *[
                    rx.select.item(opt["label"], value=opt["value"])
                    for opt in _TAB_OPTIONS
                ],
            ),
            value=AnnouncementBrowseState.tab,
            on_change=AnnouncementBrowseState.switch_tab,
            size="2",
        ),
        # Importance filter
        rx.select.root(
            rx.select.trigger(placeholder="Importance"),
            rx.select.content(
                *[
                    rx.select.item(opt["label"], value=opt["value"])
                    for opt in _IMPORTANCE_OPTIONS
                ],
            ),
            value=AnnouncementBrowseState.importance_filter,
            on_change=AnnouncementBrowseState.set_importance_filter,
            size="2",
        ),
        rx.input(
            type="date",
            value=AnnouncementBrowseState.date_from,
            on_change=AnnouncementBrowseState.set_date_from,
            size="2",
            placeholder="From",
        ),
        rx.input(
            type="date",
            value=AnnouncementBrowseState.date_to,
            on_change=AnnouncementBrowseState.set_date_to,
            size="2",
            placeholder="To",
        ),
        primary_btn(
            rx.icon("search", size=13),
            " Apply",
            on_click=AnnouncementBrowseState.apply_filters,
            size="2",
        ),
        align="center",
        gap="0.75rem",
        margin_bottom="1rem",
        flex_wrap="wrap",
        width="100%",
    )


def _audience_checkbox(grp: rx.Var) -> rx.Component:
    return rx.hstack(
        rx.checkbox(
            checked=AnnouncementComposerState.selected_audience_codes.contains(  # type: ignore[attr-defined]
                grp["code"]
            ),
            on_change=AnnouncementComposerState.toggle_audience(grp["code"]),
        ),
        rx.text(grp["name"], font_size="0.9rem"),
        gap="0.5rem",
        align="center",
    )


def _role_option(code: rx.Var) -> rx.Component:
    return rx.select.item(code, value=code)


def _category_option(cat: rx.Var) -> rx.Component:
    return rx.select.item(cat["name"], value=cat["code"])


def _composer_modal() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.heading("New Announcement", size="4"),
            rx.form(
                rx.vstack(
                    # Role
                    rx.vstack(
                        rx.text("Composing as", font_size="0.85rem", font_weight="600"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select your role"),
                            rx.select.content(
                                rx.foreach(
                                    AnnouncementComposerState.available_role_codes,
                                    _role_option,
                                )
                            ),
                            value=AnnouncementComposerState.form_role_code,
                            on_change=AnnouncementComposerState.set_form_role_code,
                            width="100%",
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Category
                    rx.vstack(
                        rx.text("Category", font_size="0.85rem", font_weight="600"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Select category"),
                            rx.select.content(
                                rx.foreach(
                                    AnnouncementComposerState.available_categories,
                                    _category_option,
                                )
                            ),
                            value=AnnouncementComposerState.form_category_code,
                            on_change=AnnouncementComposerState.set_form_category_code,
                            width="100%",
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Title
                    rx.vstack(
                        rx.text("Title", font_size="0.85rem", font_weight="600"),
                        rx.input(
                            name="form_title",
                            placeholder="Announcement title",
                            value=AnnouncementComposerState.form_title,
                            on_change=AnnouncementComposerState.set_form_title,
                            width="100%",
                            max_length=255,
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Body
                    rx.vstack(
                        rx.text("Body", font_size="0.85rem", font_weight="600"),
                        rx.text_area(
                            name="form_body_text",
                            placeholder="Announcement body text",
                            value=AnnouncementComposerState.form_body_text,
                            on_change=AnnouncementComposerState.set_form_body_text,
                            width="100%",
                            rows="5",
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Importance
                    rx.vstack(
                        rx.text("Importance", font_size="0.85rem", font_weight="600"),
                        rx.select.root(
                            rx.select.trigger(placeholder="Importance"),
                            rx.select.content(
                                rx.select.item("Normal", value="normal"),
                                rx.select.item("Very Important", value="very_important"),
                            ),
                            value=AnnouncementComposerState.form_importance,
                            on_change=AnnouncementComposerState.set_form_importance,
                            width="100%",
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Scheduled at
                    rx.vstack(
                        rx.text(
                            "Schedule (optional — defaults to now)",
                            font_size="0.85rem",
                            font_weight="600",
                        ),
                        rx.input(
                            type="datetime-local",
                            name="form_scheduled_at",
                            value=AnnouncementComposerState.form_scheduled_at,
                            on_change=AnnouncementComposerState.set_form_scheduled_at,
                            width="100%",
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Audience groups
                    rx.vstack(
                        rx.text("Audience Groups", font_size="0.85rem", font_weight="600"),
                        rx.text(
                            "Select one or more groups that will receive this announcement.",
                            font_size="0.78rem",
                            color="var(--color-muted)",
                        ),
                        rx.box(
                            rx.foreach(
                                AnnouncementComposerState.available_audience_groups,
                                _audience_checkbox,
                            ),
                            max_height="180px",
                            overflow_y="auto",
                            border="1px solid var(--color-rule)",
                            border_radius="var(--radius-2)",
                            padding="0.5rem",
                            width="100%",
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Attachment (optional)
                    rx.vstack(
                        rx.text("Attachment (optional)", font_size="0.85rem", font_weight="600"),
                        file_upload_zone(
                            on_drop=AnnouncementComposerState.stage_attachment_file,
                            accept={
                                "application/pdf": [".pdf"],
                                "image/png": [".png"],
                                "image/jpeg": [".jpg", ".jpeg"],
                            },
                            label="Drop a PDF or image, or click to browse (max 2 MB)",
                        ),
                        rx.cond(
                            AnnouncementComposerState.staged_attachment_name != "",
                            rx.text(
                                "Selected: ",
                                AnnouncementComposerState.staged_attachment_name,
                                color="var(--color-accent)",
                                font_size="0.875rem",
                            ),
                            rx.fragment(),
                        ),
                        align="start",
                        width="100%",
                        gap="0.25rem",
                    ),
                    # Buttons
                    rx.hstack(
                        primary_btn("Post Announcement", type="submit"),
                        secondary_btn(
                            "Cancel",
                            on_click=AnnouncementComposerState.clear_form,
                            type="button",
                        ),
                        gap="0.75rem",
                        margin_top="0.5rem",
                    ),
                    gap="1rem",
                    width="100%",
                ),
                on_submit=AnnouncementComposerState.save,
                reset_on_submit=False,
            ),
            gap="1rem",
            align="start",
            width="100%",
        ),
        is_open=AnnouncementComposerState.show_composer,
        max_width="560px",
    )


def _detail_panel() -> rx.Component:
    return form_modal(
        content=rx.vstack(
            rx.hstack(
                rx.heading(
                    AnnouncementDetailState.detail["title"],
                    size="4",
                ),
                rx.spacer(),
                secondary_btn(
                    rx.icon("x", size=14),
                    on_click=AnnouncementDetailState.close_detail,
                    type="button",
                    variant="ghost",
                    size="1",
                ),
                align="center",
                width="100%",
            ),
            # Metadata row
            rx.hstack(
                rx.badge(
                    AnnouncementDetailState.detail["category_code"],
                    color_scheme="indigo",
                    variant="soft",
                ),
                rx.cond(
                    AnnouncementDetailState.detail["importance"] == "very_important",
                    rx.badge("Very Important", color_scheme="red"),
                    rx.badge("Normal", color_scheme="gray"),
                ),
                rx.cond(
                    AnnouncementDetailState.detail["is_withdrawn"],
                    rx.badge("Withdrawn", color_scheme="gray", variant="outline"),
                    rx.fragment(),
                ),
                flex_wrap="wrap",
                gap="0.5rem",
            ),
            rx.text(
                "Scheduled: ",
                AnnouncementDetailState.detail["scheduled_at"],
                font_size="0.85rem",
                color="var(--color-muted)",
            ),
            rx.text(
                "By role: ",
                AnnouncementDetailState.detail["composer_role_code"],
                font_size="0.85rem",
                color="var(--color-muted)",
            ),
            rx.divider(),
            # Body text
            rx.text(
                AnnouncementDetailState.detail["message_text"],
                font_size="0.95rem",
                white_space="pre-wrap",
            ),
            # Attachments
            rx.cond(
                AnnouncementDetailState.attachments.length() > 0,  # type: ignore[attr-defined]
                rx.vstack(
                    rx.text(
                        "Attachments",
                        font_size="0.85rem",
                        font_weight="600",
                        color="var(--color-muted)",
                    ),
                    rx.foreach(
                        AnnouncementDetailState.attachments,
                        lambda att: rx.link(
                            rx.hstack(
                                rx.icon("paperclip", size=13),
                                rx.text(att["original_name"], font_size="0.875rem"),
                                gap="0.35rem",
                                align="center",
                            ),
                            href=DOWNLOAD_PREFIX + att["file_id"],
                            target="_blank",
                            color="var(--color-primary)",
                            text_decoration="none",
                            _hover={"text_decoration": "underline"},
                        ),
                    ),
                    align="start",
                    gap="0.4rem",
                    width="100%",
                ),
                rx.fragment(),
            ),
            # Withdraw button — only own, non-withdrawn announcements
            rx.cond(
                AnnouncementDetailState.detail["is_own"]
                & ~AnnouncementDetailState.detail["is_withdrawn"],
                destructive_btn(
                    rx.icon("trash-2", size=13),
                    " Withdraw",
                    on_click=AnnouncementDetailState.withdraw(
                        AnnouncementDetailState.detail["id"]
                    ),
                    type="button",
                    margin_top="0.5rem",
                ),
                rx.fragment(),
            ),
            # Flash inside detail panel
            rx.cond(
                AnnouncementDetailState.flash != "",
                config_toast(
                    AnnouncementDetailState.flash,
                    AnnouncementDetailState.flash_type,
                    AnnouncementDetailState.dismiss_flash,
                ),
                rx.fragment(),
            ),
            gap="0.75rem",
            align="start",
            width="100%",
        ),
        is_open=AnnouncementDetailState.show_detail,
        max_width="600px",
    )


def announcements_page() -> rx.Component:
    content = rx.vstack(
        nav_shell(),
        rx.box(
            # Page header
            rx.hstack(
                rx.heading(
                    "Announcements",
                    size="5",
                    font_family="var(--font-sans)",
                ),
                rx.spacer(),
                primary_btn(
                    rx.icon("plus", size=14),
                    " New Announcement",
                    on_click=AnnouncementComposerState.open_composer,
                ),
                align="center",
                width="100%",
                margin_bottom="1.5rem",
            ),
            # Composer flash (non-modal state — eligibility error shown here)
            rx.cond(
                AnnouncementComposerState.flash != "",
                config_toast(
                    AnnouncementComposerState.flash,
                    AnnouncementComposerState.flash_type,
                    AnnouncementComposerState.dismiss_flash,
                ),
                rx.fragment(),
            ),
            # Browse flash
            rx.cond(
                AnnouncementBrowseState.flash != "",
                config_toast(
                    AnnouncementBrowseState.flash,
                    AnnouncementBrowseState.flash_type,
                    AnnouncementBrowseState.dismiss_flash,
                ),
                rx.fragment(),
            ),
            # Filter strip
            _filter_strip(),
            # Summary count
            rx.text(
                rx.cond(
                    AnnouncementBrowseState.total > 0,
                    AnnouncementBrowseState.total.to_string()  # type: ignore[attr-defined]
                    + " announcement(s)",
                    "",
                ),
                font_size="0.85rem",
                color="var(--color-muted)",
                margin_bottom="0.75rem",
                font_family="var(--font-sans)",
            ),
            # Announcement list
            rx.cond(
                AnnouncementBrowseState.loading,
                rx.center(rx.spinner(), padding="2rem"),
                rx.cond(
                    AnnouncementBrowseState.rows.length() == 0,  # type: ignore[attr-defined]
                    rx.box(
                        rx.text(
                            "No announcements found.",
                            color="var(--color-muted)",
                            font_size="0.95rem",
                        ),
                        padding="2rem",
                        text_align="center",
                    ),
                    rx.vstack(
                        rx.foreach(AnnouncementBrowseState.rows, _row_card),
                        gap="0.75rem",
                        width="100%",
                    ),
                ),
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

    return rx.cond(
        AuthState.current_user_id != "",
        rx.fragment(
            content,
            _composer_modal(),
            _detail_panel(),
        ),
        rx.fragment(),
    )
