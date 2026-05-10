import reflex as rx


class BaseState(rx.State):
    """Shared state inherited by all page states.

    current_user_id is populated from the session cookie by the auth middleware
    at M1. At M0 it is a stub value set by the seed's system_admin user.
    """

    current_user_id: str = ""
    flash: str = ""

    def clear_flash(self) -> None:
        self.flash = ""
