"""The front page: pidbox's metrics in the header, and the sidebar's pages."""

from __future__ import annotations

from pathlib import Path

import invenio_pidbox
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

STARTER_TEMPLATES = Path(__file__).resolve().parents[3] / "templates" / "semantic-ui"
PIDBOX_TEMPLATES = Path(invenio_pidbox.__file__).parent / "templates" / "semantic-ui"

STUBS = {
    "header.html": "{% block navbar %}<nav></nav>{% endblock navbar %}",
    "invenio_app_rdm/frontpage_metrics.html": "<div id=metrics></div>",
    # What the front page imports and extends, as stand-ins.
    "invenio_app_rdm/macros/records_list.html": (
        "{% macro records_list(title) %}<div id=records></div>{% endmacro %}"
    ),
    "invenio_communities/macros/communities_carousel.html": (
        "{% macro communities_carousel() %}{% endmacro %}"
    ),
    "invenio_theme/frontpage.html": (
        "{% block page_header %}{% endblock %}{% block page_body %}{% endblock %}"
    ),
}

WHY = {
    "url": "/about/why",
    "title": "Why InvenioRDM Starter?",
    "description": "",
    "content": "<ul><li>Running in 15 minutes</li></ul>",
}


def _environment(pages: dict | None) -> Environment:
    environment = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(STUBS),
                FileSystemLoader(str(STARTER_TEMPLATES)),
                FileSystemLoader(str(PIDBOX_TEMPLATES)),
            ]
        )
    )
    environment.globals["_"] = lambda text: text
    if pages is not None:
        environment.globals["starter_page"] = pages.get
    return environment


def _settings(**config: object) -> dict:
    return {
        "THEME_HEADER_TEMPLATE": "header.html",
        "THEME_FRONTPAGE_TITLE": "InvenioRDM Starter",
        "THEME_FRONTPAGE_SUBTITLE": "A starter project.",
        "PIDBOX_FRONTPAGE_METRICS": True,
        "PIDBOX_FRONTPAGE_METRICS_BACKGROUND": "#cbd5e1",
        "STARTER_FRONTPAGE_SIDEBAR_PAGES": ["/about/why", "/missing"],
        **config,
    }


def _render_frontpage(pages: dict | None, **config: object) -> str:
    template = _environment(pages).get_template("invenio_app_rdm/frontpage.html")
    return template.render(config=_settings(**config), show_intro_section=False)


def test_the_header_shows_the_metrics_without_title_or_subtitle() -> None:
    html = _render_frontpage({"/about/why": WHY})

    assert "<div id=metrics>" in html
    assert "InvenioRDM Starter</h1>" not in html
    assert "A starter project." not in html


def test_the_sidebar_shows_a_box_per_page_that_exists() -> None:
    html = _render_frontpage({"/about/why": WHY})

    assert html.count("starter-frontpage-page") == 1
    assert ">Why InvenioRDM Starter?</h2>" in html
    assert "<ul><li>Running in 15 minutes</li></ul>" in html


def test_the_sidebar_is_empty_without_pages() -> None:
    assert "starter-frontpage-page" not in _render_frontpage({})
    assert "starter-frontpage-page" not in _render_frontpage(None)
