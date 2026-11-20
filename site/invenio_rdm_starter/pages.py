"""The front page's sidebar, from pages an admin edits like any other.

The boxes of the front page's sidebar are invenio-pages pages
(Administration > Site management > Pages), so that they're changed without
a deploy, in every language the site has. ``STARTER_FRONTPAGE_SIDEBAR_PAGES``
lists them (``/about/why``), one box each, the page's title as its header
and its content as the box. The Starter ships them as fixtures
(``app_data/pages.yaml``).

Templates read them with ``starter_page(url)``, which a finalize hook makes
a template global.
"""

from __future__ import annotations

from typing import Any

import structlog
from flask import Flask, current_app
from invenio_access.permissions import system_identity
from invenio_i18n import get_locale
from invenio_pages.proxies import current_pages_service
from invenio_pages.records.errors import PageNotFoundError


def _languages() -> list[str]:
    """The current language, then the site's default, without repeats."""
    languages = []
    locale = get_locale()
    if locale is not None:
        languages.append(locale.language)
    default = current_app.config.get("BABEL_DEFAULT_LOCALE", "en")
    if default not in languages:
        languages.append(default)
    return languages


def read_page(url: str | None) -> dict[str, Any] | None:
    """The page at ``url`` in the current language, or the default one.

    ``None`` when there is no such page, as before the fixtures are loaded:
    the front page then shows what it would without pages. Pages are public,
    so they're read as the system.
    """
    if not url:
        return None
    for language in _languages():
        try:
            return current_pages_service.read_by_url(
                system_identity, url, language
            ).to_dict()
        except PageNotFoundError:
            continue
    return None


def finalize_app(app: Flask) -> None:
    """Make ``starter_page`` a template global.

    Loaded through the ``invenio_base.finalize_app`` entry point
    ``invenio_rdm_starter_pages``.
    """
    app.add_template_global(read_page, "starter_page")
    structlog.get_logger().bind(service="invenio-rdm-starter").debug(
        "template_global_added", name="starter_page"
    )
