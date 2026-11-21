"""The front page: the About box above pidbox's metrics, and the sidebar's pages."""

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
    "invenio_theme/frontpage.html": (
        "{% block page_header %}{% endblock %}{% block page_body %}{% endblock %}"
    ),
}

ABOUT = {
    "url": "/about",
    "title": "About InvenioRDM Starter",
    "description": "What InvenioRDM Starter archives.",
    "content": (
        "<p>Metadata and content from the Journal of Open Source Software "
        '(<a href="http://joss.theoj.org/">JOSS</a>) archived in InvenioRDM Starter</p>'
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
        "STARTER_FRONTPAGE_ABOUT_PAGE": "/about",
        "STARTER_FRONTPAGE_SIDEBAR_PAGES": ["/about/why", "/missing"],
        **config,
    }


def _render_frontpage(
    pages: dict | None, total: int | None = 3, **config: object
) -> str:
    """The front page, with ``total`` records (``None``: the count is unknown)."""
    environment = _environment(pages)
    environment.globals["starter_records_total"] = lambda: total
    template = environment.get_template("invenio_app_rdm/frontpage.html")
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


@pytest.mark.parametrize("total", [3, None])
def test_with_records_or_an_unknown_count_the_page_is_as_always(total) -> None:
    html = _render_frontpage({}, total=total)

    assert "<div id=metrics>" in html
    assert "<div id=records>" in html
    assert "starter-no-records" not in html


def test_without_records_no_metrics_band_and_a_message() -> None:
    html = _render_frontpage({"/about/why": WHY}, total=0)

    assert "<nav></nav>" in html  # the plain header
    assert "frontpage-search-bar" not in html
    assert "<div id=metrics>" not in html
    assert "<div id=records>" not in html
    assert "No works have been published yet." in html
    # The sidebar stays.
    assert ">Why InvenioRDM Starter?</h2>" in html


def test_the_about_page_is_a_box_above_the_metrics() -> None:
    html = _render_frontpage({"/about": ABOUT, "/about/why": WHY})

    box = html.index("starter-frontpage-about")
    assert box < html.index("<div id=metrics>")
    assert '(<a href="http://joss.theoj.org/">JOSS</a>) archived in' in html
    # The page's content, not its title or description.
    assert "About InvenioRDM Starter" not in html
    assert "What InvenioRDM Starter archives." not in html


@pytest.mark.parametrize(
    ("pages", "config"),
    [
        ({"/about/why": WHY}, {}),  # no About page yet
        ({"/about": {**ABOUT, "content": ""}}, {}),  # an About page left empty
        ({"/about": ABOUT}, {"STARTER_FRONTPAGE_ABOUT_PAGE": None}),  # switched off
        (None, {}),  # no pages at all
    ],
)
def test_no_about_box_without_its_content(pages, config) -> None:
    html = _render_frontpage(pages, **config)

    assert "starter-frontpage-about" not in html
    assert "<div id=metrics>" in html


def test_without_records_no_about_box_either() -> None:
    html = _render_frontpage({"/about": ABOUT}, total=0)

    assert "starter-frontpage-about" not in html


@pytest.mark.parametrize(
    ("language", "text"),
    [
        ("", "This is a demo site and content and metadata are regularly cleared."),
        (
            ".de",
            "Dies ist eine Demo-Seite, Inhalte und Metadaten werden regelmäßig gelöscht.",
        ),
        (".fr", "les contenus et les métadonnées sont régulièrement effacés."),
        (".es", "el contenido y los metadatos se borran periódicamente."),
    ],
)
def test_the_about_page_fixture_is_translated(language, text) -> None:
    fixture = (
        STARTER_TEMPLATES.parents[1] / "app_data" / "pages" / f"about.html{language}"
    )

    content = fixture.read_text()
    assert text in content
    assert '(<a href="http://joss.theoj.org/">JOSS</a>)' in content
