"""Faculty self-service profile page (/faculty/profile) — M10 Phase P1.

Cards:
  - Identity readonly (employee_id, title, names, designation, dept, campus, joining_date)
  - Contact editable (phone, whatsapp, alt_phone, alt_email, emergency contact fields)
  - External IDs editable (orcid, linkedin, google_scholar, researchgate)
  - PhD editable (is_phd toggle + conditional 4 fields; toggle-off confirmation dialog)
"""

from __future__ import annotations

import reflex as rx

from durgam.pages.components import (
    config_toast,
    nav_shell,
    primary_btn,
)
from durgam.pages.shared.confirmation_dialog import confirmation_dialog
from durgam.states.auth import AuthState
from durgam.states.faculty_profile import FacultyProfileState


def _kv_row(label: str, value: rx.Var | str) -> rx.Component:
    return rx.hstack(
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
        padding="0.35rem 0",
    )


def _card(title: str, *children: rx.Component) -> rx.Component:
    return rx.box(
        rx.heading(title, size="4", margin_bottom="1rem", color="var(--color-body)"),
        *children,
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="1.5rem",
        width="100%",
    )


def _identity_card() -> rx.Component:
    return _card(
        "Identity",
        _kv_row("Employee ID", FacultyProfileState.employee_id),
        _kv_row("Title", FacultyProfileState.title),
        _kv_row("First Name", FacultyProfileState.first_name),
        _kv_row("Middle Name", FacultyProfileState.middle_name),
        _kv_row("Last Name", FacultyProfileState.last_name),
        _kv_row("Designation", FacultyProfileState.designation_label),
        _kv_row("Department", FacultyProfileState.department_label),
        _kv_row("Campus", FacultyProfileState.campus_label),
        _kv_row("Joining Date", FacultyProfileState.joining_date_display),
        rx.cond(
            FacultyProfileState.is_vacation_employee,
            _kv_row("Vacation Employee", "Yes"),
            _kv_row("Vacation Employee", "No"),
        ),
        rx.text(
            "Identity fields are managed by Registrar / HR Head.",
            font_size="0.75rem",
            color="var(--color-muted)",
            margin_top="0.75rem",
        ),
    )


def _input_row(
    label: str,
    value: rx.Var,
    on_change,
    placeholder: str = "",
    required: bool = False,
) -> rx.Component:
    return rx.vstack(
        rx.hstack(
            rx.text(label, font_size="0.85rem", font_weight="600", color="var(--color-body)"),
            rx.cond(required, rx.text("*", color="var(--color-destructive)", font_size="0.85rem"), rx.fragment()),
            gap="0.25rem",
            align="center",
        ),
        rx.input(
            value=value,
            on_change=on_change,
            placeholder=placeholder,
            font_size="0.9rem",
            font_family="var(--font-sans)",
            border="1px solid var(--color-rule)",
            border_radius="4px",
            padding="0.4rem 0.6rem",
            width="100%",
        ),
        align="start",
        gap="0.25rem",
        width="100%",
    )


def _contact_card() -> rx.Component:
    return _card(
        "Contact Information",
        rx.vstack(
            _input_row(
                "Phone",
                FacultyProfileState.phone,
                FacultyProfileState.set_phone,
                placeholder="Primary phone number",
                required=True,
            ),
            _input_row(
                "WhatsApp",
                FacultyProfileState.whatsapp,
                FacultyProfileState.set_whatsapp,
                placeholder="WhatsApp number (optional)",
            ),
            _input_row(
                "Alternate Phone",
                FacultyProfileState.alt_phone,
                FacultyProfileState.set_alt_phone,
                placeholder="Alternate phone (optional)",
            ),
            _input_row(
                "Alternate Email",
                FacultyProfileState.alt_email,
                FacultyProfileState.set_alt_email,
                placeholder="Alternate email (optional)",
            ),
            rx.box(
                rx.text(
                    "Emergency Contact",
                    font_size="0.9rem",
                    font_weight="700",
                    color="var(--color-body)",
                    margin_bottom="0.5rem",
                ),
                _input_row(
                    "Name",
                    FacultyProfileState.emergency_contact_name,
                    FacultyProfileState.set_emergency_contact_name,
                    placeholder="Emergency contact name",
                    required=True,
                ),
                _input_row(
                    "Relation",
                    FacultyProfileState.emergency_contact_relation,
                    FacultyProfileState.set_emergency_contact_relation,
                    placeholder="E.g. Spouse, Parent",
                    required=True,
                ),
                _input_row(
                    "Phone",
                    FacultyProfileState.emergency_contact_phone,
                    FacultyProfileState.set_emergency_contact_phone,
                    placeholder="Emergency contact phone",
                    required=True,
                ),
                border_top="1px solid var(--color-rule)",
                padding_top="0.75rem",
                margin_top="0.75rem",
                width="100%",
            ),
            rx.hstack(
                primary_btn(
                    "Save Contact",
                    on_click=FacultyProfileState.save_contact,
                    type="button",
                ),
                gap="0.75rem",
                margin_top="1rem",
            ),
            gap="0.75rem",
            align="start",
            width="100%",
        ),
    )


def _external_ids_card() -> rx.Component:
    return _card(
        "External Profiles & IDs",
        rx.vstack(
            _input_row(
                "ORCID",
                FacultyProfileState.orcid,
                FacultyProfileState.set_orcid,
                placeholder="https://orcid.org/0000-0000-0000-0000",
            ),
            _input_row(
                "LinkedIn",
                FacultyProfileState.linkedin,
                FacultyProfileState.set_linkedin,
                placeholder="LinkedIn profile URL",
            ),
            _input_row(
                "Google Scholar",
                FacultyProfileState.google_scholar,
                FacultyProfileState.set_google_scholar,
                placeholder="Google Scholar profile URL",
            ),
            _input_row(
                "ResearchGate",
                FacultyProfileState.researchgate,
                FacultyProfileState.set_researchgate,
                placeholder="ResearchGate profile URL",
            ),
            rx.hstack(
                primary_btn(
                    "Save External IDs",
                    on_click=FacultyProfileState.save_external_ids,
                    type="button",
                ),
                gap="0.75rem",
                margin_top="1rem",
            ),
            gap="0.75rem",
            align="start",
            width="100%",
        ),
    )


def _phd_card() -> rx.Component:
    return _card(
        "PhD Details",
        rx.vstack(
            rx.vstack(
                rx.hstack(
                    rx.checkbox(
                        checked=FacultyProfileState.is_phd,
                        on_change=FacultyProfileState.set_is_phd_with_confirm,
                    ),
                    rx.text("I hold a PhD degree", font_size="0.9rem"),
                    align="center",
                    gap="0.5rem",
                ),
                rx.text(
                    "Unchecking this will clear all PhD details after confirmation.",
                    font_size="0.75rem",
                    color="var(--color-muted)",
                ),
                align="start",
                gap="0.25rem",
                margin_bottom="0.75rem",
                width="100%",
            ),
            rx.cond(
                FacultyProfileState.is_phd,
                rx.vstack(
                    _input_row(
                        "Thesis Title",
                        FacultyProfileState.phd_thesis_title,
                        FacultyProfileState.set_phd_thesis_title,
                        placeholder="Full thesis title",
                    ),
                    _input_row(
                        "Registration Number",
                        FacultyProfileState.phd_registration_number,
                        FacultyProfileState.set_phd_registration_number,
                        placeholder="PhD registration number",
                    ),
                    _input_row(
                        "Awarding Institution",
                        FacultyProfileState.phd_awarding_institution,
                        FacultyProfileState.set_phd_awarding_institution,
                        placeholder="Name of the awarding university",
                    ),
                    _input_row(
                        "Year of Award",
                        FacultyProfileState.phd_year_str,
                        FacultyProfileState.set_phd_year_str,
                        placeholder="YYYY",
                    ),
                    gap="0.75rem",
                    align="start",
                    width="100%",
                ),
                rx.fragment(),
            ),
            rx.hstack(
                primary_btn(
                    "Save PhD Details",
                    on_click=FacultyProfileState.save_phd,
                    type="button",
                ),
                gap="0.75rem",
                margin_top="1rem",
            ),
            gap="0.5rem",
            align="start",
            width="100%",
        ),
    )


def _no_faculty_record_message() -> rx.Component:
    return rx.box(
        rx.heading("No Faculty Profile", size="5", margin_bottom="0.75rem"),
        rx.text(
            "You do not have a Faculty profile in this system. "
            "Contact the Registrar's office if this is an error.",
            color="var(--color-muted)",
            font_size="0.9rem",
        ),
        background="white",
        border="1px solid var(--color-rule)",
        border_radius="8px",
        padding="2rem",
        width="100%",
    )


def _clear_phd_confirm_dialog() -> rx.Component:
    return confirmation_dialog(
        is_open=FacultyProfileState.show_clear_phd_confirm,
        title="Clear PhD details?",
        body=(
            "This will set 'I hold a PhD' to No and clear your thesis title, "
            "registration number, awarding institution, and year of award. "
            "This change will be saved immediately."
        ),
        on_confirm=FacultyProfileState.confirm_clear_phd,
        on_cancel=FacultyProfileState.cancel_clear_phd,
        confirm_label="Yes, clear PhD details",
        cancel_label="Cancel",
        danger=True,
    )


def faculty_profile_page() -> rx.Component:
    return rx.cond(
        AuthState.current_user_id != "",
        rx.vstack(
            nav_shell(),
            rx.box(
                rx.vstack(
                    rx.heading("My Profile", size="6", margin_bottom="0.5rem"),
                    rx.cond(
                        FacultyProfileState.loading,
                        rx.center(rx.spinner(), padding="4rem"),
                        rx.cond(
                            ~FacultyProfileState.has_faculty_record,
                            _no_faculty_record_message(),
                            rx.vstack(
                                _identity_card(),
                                _contact_card(),
                                _external_ids_card(),
                                _phd_card(),
                                _clear_phd_confirm_dialog(),
                                spacing="4",
                                width="100%",
                            ),
                        ),
                    ),
                    align="start",
                    width="100%",
                    max_width="720px",
                    margin="0 auto",
                    padding="1.5rem 1rem",
                ),
                width="100%",
                min_height="calc(100vh - 56px)",
                background="var(--color-surface)",
            ),
            config_toast(
                FacultyProfileState.flash,
                FacultyProfileState.flash_type,
                FacultyProfileState.dismiss_flash,
            ),
            spacing="0",
            width="100%",
        ),
        rx.fragment(),
    )
