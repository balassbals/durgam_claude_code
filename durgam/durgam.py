import reflex as rx

from durgam.config import settings
from durgam.logging import configure_logging
from durgam.pages.index import index
from durgam.theme import apply_theme

configure_logging(debug=settings.debug)

app = rx.App(style=apply_theme())
app.add_page(index, route="/")
