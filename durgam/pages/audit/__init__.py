"""Audit module nav registration (M6b).

Import this module to register the audit nav entry. Called from durgam.py.
"""

from durgam.nav.registry import NavEntry, register

register(NavEntry(
    label="Audit Log",
    href="/audit",
    icon="scroll-text",
    group="Admin",
    permission_action="read",
    permission_resource="audit_log",
))
