import reflex as rx


class BaseState(rx.State):
    """Shared state inherited by all page states."""

    # Opaque session token stored in the browser cookie (SD-001).
    # rx.Cookie is JS-set; see docs/security_decisions.md for HttpOnly gap analysis.
    session_token: str = rx.Cookie(  # type: ignore[assignment]
        name="dsession",
        same_site="lax",
        secure=True,
        max_age=7 * 24 * 3600,
        path="/",
    )

    # Populated by AuthState.resolve_session() on each page load.
    current_user_id: str = ""
    current_username: str = ""
    current_role_code: str = ""

    flash: str = ""

    # Request metadata populated by auth middleware / Reflex router data.
    client_ip: str = ""
    client_user_agent: str = ""
    request_id: str = ""

    def clear_flash(self) -> None:
        self.flash = ""
