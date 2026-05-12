import reflex as rx

from durgam.config import settings
from durgam.logging import configure_logging
from durgam.pages.change_password import change_password
from durgam.pages.forgot_password import forgot_password
from durgam.pages.index import index
from durgam.pages.login import login
from durgam.pages.reset_password import reset_password
from durgam.states.auth import AuthState
from durgam.theme import apply_theme

configure_logging(debug=settings.debug)

app = rx.App(style=apply_theme())
app.add_page(index, route="/")
app.add_page(login, route="/login", on_load=AuthState.resolve_session)
app.add_page(forgot_password, route="/forgot-password")
app.add_page(
    reset_password,
    route="/reset-password",
    on_load=[AuthState.resolve_session, AuthState.load_reset_token],
)
app.add_page(
    change_password,
    route="/change-password",
    on_load=AuthState.resolve_session,
)
