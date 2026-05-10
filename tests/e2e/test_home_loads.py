"""E2E smoke test: home page loads and CSS variables are applied.

Requires a running Reflex app (see docs/runbook.md).
In CI: set BASE_URL env var to the running app URL; skip if not set.
"""

import os

import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "")

pytestmark = pytest.mark.skipif(
    not BASE_URL,
    reason="BASE_URL not set — start the app and set BASE_URL=http://localhost:3000",
)


def test_home_page_loads(page: Page):
    page.goto(BASE_URL)
    expect(page).not_to_have_title("")


def test_css_variables_applied(page: Page):
    page.goto(BASE_URL)
    accent = page.evaluate(
        "getComputedStyle(document.body).getPropertyValue('--color-accent').trim()"
    )
    assert accent == "#C75B12", f"Expected #C75B12 got {accent!r}"


def test_no_console_errors(page: Page):
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto(BASE_URL)
    page.wait_for_load_state("networkidle")
    assert not errors, f"Console errors: {errors}"
