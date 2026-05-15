from uuid import UUID

import reflex as rx

from durgam.db import open_session
from durgam.nav.registry import get_visible_entries


class BaseState(rx.State):
    """Shared state inherited by all page states."""

    # Opaque session token stored in the browser cookie (SD-001).
    # rx.Cookie is JS-set; see docs/security_decisions.md for HttpOnly gap analysis.
    session_token: str = rx.Cookie(
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

    # Nav entries visible to the current user (cached at login; re-populated on load).
    # Each entry is {"label": str, "href": str, "icon": str, "group": str}.
    visible_nav_entries: list[dict[str, str]] = []

    def clear_flash(self) -> None:
        self.flash = ""

    def _load_nav_entries(self) -> None:
        """Populate visible_nav_entries for the current user.

        Called by page on_load handlers after _resolve_session_state() sets
        current_user_id. No-op if the user is not authenticated.
        """
        if not self.current_user_id:
            self.visible_nav_entries = []
            return
        try:
            user_id = UUID(self.current_user_id)
        except ValueError:
            self.visible_nav_entries = []
            return
        with open_session() as session:
            self.visible_nav_entries = get_visible_entries(user_id, session)
