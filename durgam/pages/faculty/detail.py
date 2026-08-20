"""Faculty detail (/faculty/[faculty_id]) — M10 Phase 8A.

Read-only peer view: photo, identity, contact, external IDs, PhD, and
Education/Experience/Expertise. NO PAN/Aadhaar (deferred per TD-084), NO Documents.
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import admin_page, nav_shell, page_footer
from durgam.states.faculty_detail import FacultyDetailState


def _kv(label: str, value: rx.Var) -> rx.Component:
    return rx.cond(
        value != "",
        rx.hstack(
            rx.text(
                label,
                font_weight="600",
                font_size="0.85rem",
                color="var(--color-muted)",
                min_width="10rem",
                flex_shrink="0",
            ),
            rx.text(value, font_size="0.9rem", color="var(--color-body)"),
            gap="1rem",
            align="start",
            width="100%",
            padding="0.3rem 0",
        ),
        rx.fragment(),
    )


def _card(title: str, *children: rx.Component) -> rx.Component:
    return rx.box(
        rx.heading(title, size="4", margin_bottom="0.75rem", color="var(--color-body)"),
        *children,
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1.5rem",
        width="100%",
    )


def _avatar() -> rx.Component:
    return rx.cond(
        FacultyDetailState.photo_url != "",
        rx.image(
            src=FacultyDetailState.photo_url,
            width="120px",
            height="120px",
            object_fit="cover",
            border_radius="50%",
            border="1px solid var(--color-rule)",
        ),
        rx.box(
            rx.text(
                FacultyDetailState.initials,
                font_size="2.5rem",
                font_weight="600",
                color="white",
            ),
            width="120px",
            height="120px",
            border_radius="50%",
            background="var(--color-primary)",
            display="flex",
            align_items="center",
            justify_content="center",
        ),
    )


def _edu_row(record: dict) -> rx.Component:
    return rx.box(
        rx.text(record["degree_name"], font_weight="600", font_size="0.9rem"),
        rx.text(
            record["awarding_institution"],
            " · ",
            record["year_of_award"],
            font_size="0.8rem",
            color="var(--color-muted)",
        ),
        rx.cond(
            record["specialization"] != "",
            rx.text(record["specialization"], font_size="0.8rem", color="var(--color-muted)"),
            rx.fragment(),
        ),
        padding="0.5rem 0",
        border_bottom="1px solid var(--color-rule)",
        width="100%",
    )


def _exp_row(record: dict) -> rx.Component:
    return rx.box(
        rx.text(record["organization"], font_weight="600", font_size="0.9rem"),
        rx.text(
            record["designation_held"],
            " · ",
            record["date_range"],
            font_size="0.8rem",
            color="var(--color-muted)",
        ),
        padding="0.5rem 0",
        border_bottom="1px solid var(--color-rule)",
        width="100%",
    )


def _expertise_row(record: dict) -> rx.Component:
    return rx.hstack(
        rx.text(record["area"], font_size="0.9rem"),
        rx.cond(
            record["proficiency"] != "",
            rx.badge(record["proficiency"], color_scheme="indigo"),
            rx.fragment(),
        ),
        gap="0.5rem",
        align="center",
        padding="0.35rem 0",
        width="100%",
    )


def _detail_body() -> rx.Component:
    return rx.vstack(
        rx.box(
            rx.vstack(
                _avatar(),
                rx.heading(FacultyDetailState.name, size="6"),
                rx.text(
                    FacultyDetailState.designation,
                    font_size="0.95rem",
                    color="var(--color-muted)",
                ),
                align="center",
                gap="0.5rem",
            ),
            background="white",
            border="1px solid var(--color-rule)",
            border_radius="8px",
            padding="1.5rem",
            width="100%",
        ),
        _card(
            "Identity",
            _kv("Employee ID", FacultyDetailState.employee_id),
            _kv("Designation", FacultyDetailState.designation),
            _kv("Department", FacultyDetailState.department_code),
            _kv("Campus", FacultyDetailState.campus_code),
            _kv("Joining Date", FacultyDetailState.joining_date),
            _kv("Employee Type", FacultyDetailState.employee_type),
        ),
        _card(
            "Contact",
            _kv("Phone", FacultyDetailState.phone),
            _kv("WhatsApp", FacultyDetailState.whatsapp),
            _kv("Alternate Phone", FacultyDetailState.alt_phone),
            _kv("Alternate Email", FacultyDetailState.alt_email),
        ),
        _card(
            "External IDs",
            _kv("ORCID", FacultyDetailState.orcid),
            _kv("LinkedIn", FacultyDetailState.linkedin),
            _kv("Google Scholar", FacultyDetailState.google_scholar),
            _kv("ResearchGate", FacultyDetailState.researchgate),
        ),
        rx.cond(
            FacultyDetailState.is_phd,
            _card(
                "PhD",
                _kv("Thesis Title", FacultyDetailState.phd_thesis_title),
                _kv("Registration Number", FacultyDetailState.phd_registration_number),
                _kv("Awarding Institution", FacultyDetailState.phd_awarding_institution),
                _kv("Year of Award", FacultyDetailState.phd_year),
            ),
            rx.fragment(),
        ),
        _card(
            "Education",
            rx.cond(
                FacultyDetailState.education.length() == 0,
                rx.text("No education records.", font_size="0.85rem", color="var(--color-muted)"),
                rx.foreach(FacultyDetailState.education, _edu_row),
            ),
        ),
        _card(
            "Experience",
            rx.cond(
                FacultyDetailState.experience.length() == 0,
                rx.text("No experience records.", font_size="0.85rem", color="var(--color-muted)"),
                rx.foreach(FacultyDetailState.experience, _exp_row),
            ),
        ),
        _card(
            "Areas of Expertise",
            rx.cond(
                FacultyDetailState.expertise.length() == 0,
                rx.text("No expertise records.", font_size="0.85rem", color="var(--color-muted)"),
                rx.foreach(FacultyDetailState.expertise, _expertise_row),
            ),
        ),
        spacing="4",
        width="100%",
    )


def _content() -> rx.Component:
    return rx.vstack(
        nav_shell(),
        rx.box(
            rx.vstack(
                rx.link(
                    rx.hstack(
                        rx.icon("arrow-left", size=16),
                        rx.text("Back to Directory"),
                        align="center",
                        gap="0.4rem",
                    ),
                    href="/faculty",
                    color="var(--color-primary)",
                    font_size="0.85rem",
                ),
                rx.cond(
                    FacultyDetailState.loading,
                    rx.center(rx.spinner(), padding="3rem"),
                    rx.cond(
                        FacultyDetailState.not_found,
                        rx.box(
                            rx.heading("Faculty not found", size="5"),
                            rx.text(
                                "No faculty record exists for this link.",
                                color="var(--color-muted)",
                                font_size="0.9rem",
                            ),
                            background="white",
                            border="1px solid var(--color-rule)",
                            border_radius="8px",
                            padding="2rem",
                            width="100%",
                        ),
                        _detail_body(),
                    ),
                ),
                spacing="4",
                width="100%",
                align="start",
            ),
            padding="2rem",
            max_width="900px",
            margin="0 auto",
            width="100%",
        ),
        page_footer(),
        align="start",
        width="100%",
    )


def faculty_detail_page() -> rx.Component:
    return admin_page(_content())
