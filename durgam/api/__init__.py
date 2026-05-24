"""Custom API routes mounted on Reflex's Starlette underpinning."""

from urllib.parse import urlparse

import reflex as rx

_cfg = rx.config.get_config()
_api = urlparse(_cfg.api_url)
_deploy = urlparse(_cfg.deploy_url)

DOWNLOAD_PREFIX: str = (
    "" if (_api.hostname == _deploy.hostname and _api.port == _deploy.port)
    else _cfg.api_url
)
