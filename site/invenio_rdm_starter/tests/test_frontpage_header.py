"""The front page: the subtitle above pidbox's metrics, and the sidebar's pages."""

from __future__ import annotations

from pathlib import Path

import invenio_pidbox
import pytest
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
    "invenio_theme/frontpage.html": "{% block page_body %}{% endblock %}",
}

ABOUT = {
    "url": "/about",
    "title": "About InvenioRDM Starter",
    "description": "A repository of open source software papers.",
    "content": "<p>About.</p>",
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
        "STARTER_FRONTPAGE_ABOUT_PAGE": "/about",
        "STARTER_FRONTPAGE_SIDEBAR_PAGES": ["/about/why", "/missing"],
        **config,
    }


def _render(pages: dict | None = None, **config: object) -> str:
    """The header, without pages unless given (url -> page)."""
    template = _environment(pages).get_template(
        "invenio_rdm_starter/header_frontpage.html"
    )
    return template.render(config=_settings(**config))


def _render_frontpage(pages: dict | None, **config: object) -> str:
    template = _environment(pages).get_template("invenio_app_rdm/frontpage.html")
    return template.render(config=_settings(**config), show_intro_section=False)


def test_the_subtitle_sits_above_the_metrics_without_the_title() -> None:
    html = _render()

    assert html.index("A starter project.") < html.index("<div id=metrics>")
    # The menubar's logo already names the site.
    assert "InvenioRDM Starter" not in html
    assert "inverted" not in html  # dark ink on the light band


@pytest.mark.parametrize(
    "config",
    [
        {"PIDBOX_FRONTPAGE_METRICS": False},
        {"PIDBOX_FRONTPAGE_METRICS_BACKGROUND": None},
    ],
)
def test_the_subtitle_stays_white_on_the_theme_band(config: dict) -> None:
    html = _render(**config)

    assert "A starter project." in html
    assert "header inverted" in html


def test_no_row_without_a_subtitle() -> None:
    html = _render(THEME_FRONTPAGE_SUBTITLE="")

    assert "starter-frontpage-title" not in html
    assert "<div id=metrics>" in html


def test_the_about_page_gives_the_subtitle_and_a_link() -> None:
    html = _render({"/about": ABOUT})

    assert "A repository of open source software papers." in html
    assert "A starter project." not in html
    assert 'href="/about">About this repository</a>' in html


def test_without_the_about_page_the_subtitle_is_the_setting() -> None:
    html = _render({}, STARTER_FRONTPAGE_ABOUT_PAGE="/about")

    assert "A starter project." in html
    assert "About this repository" not in html


def test_the_sidebar_shows_a_box_per_page_that_exists() -> None:
    html = _render_frontpage({"/about/why": WHY})

    assert html.count("starter-frontpage-page") == 1
    assert ">Why InvenioRDM Starter?</h2>" in html
    assert "<ul><li>Running in 15 minutes</li></ul>" in html


def test_the_sidebar_is_empty_without_pages() -> None:
    assert "starter-frontpage-page" not in _render_frontpage({})
    assert "starter-frontpage-page" not in _render_frontpage(None)
