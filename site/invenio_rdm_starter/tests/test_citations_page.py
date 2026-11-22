"""Tests for a record's citations, a page at a time."""

from pathlib import Path

import pytest
from flask import Flask
from invenio_rdm_starter import citations as starter_citations
from invenio_rdm_starter.citations import citation_count, citations_page, page_number
from jinja2 import ChoiceLoader, FileSystemLoader

ROOT = Path(__file__).parents[3]


def _app() -> Flask:
    app = Flask(__name__)
    app.config["STARTER_CITATIONS_PAGE_SIZE"] = 25
    app.config["PIDBOX_SQLITE_PATH"] = "/store.sqlite3"
    app.jinja_loader = ChoiceLoader(
        [FileSystemLoader(str(ROOT / "templates/semantic-ui"))]
    )
    app.jinja_env.globals["_"] = lambda text, **kwargs: text % kwargs
    app.jinja_env.filters["sanitize_html"] = lambda value, **kwargs: value
    # The macros' other filters, which these macros don't use.
    for name in ("custom_fields_search", "format_edtf", "get_scheme_label"):
        app.jinja_env.filters[name] = lambda value, *args, **kwargs: value
    app.jinja_env.filters["pid_url"] = lambda value, scheme=None: (
        f"https://doi.org/{value}"
    )
    app.add_url_rule(
        "/records/<pid_value>/citations",
        endpoint="invenio_rdm_starter.record_citations",
    )
    app.add_url_rule("/search", endpoint="invenio_search_ui.search")
    app.add_url_rule(
        "/communities/<pid_value>/records",
        endpoint="invenio_app_rdm_communities.communities_detail",
    )
    return app


def _citations(count: int) -> list[dict]:
    return [
        {"identifier": f"10.5555/{n}", "scheme": "doi", "reference": f"Work {n}."}
        for n in range(1, count + 1)
    ]


def _render(count: int, page: int, size: int = 25, stored: int | None = None) -> str:
    fields = {"pidbox:citations": _citations(count if stored is None else stored)}
    if stored is not None:
        fields["pidbox:citation_count"] = count
    app = _app()
    with app.test_request_context():
        return app.jinja_env.get_template("invenio_rdm_starter/citations.html").render(
            citations=citations_page(fields, "10.5555/cited", page, size),
            record_id="t5wk7-bsp06",
            community_slug=None,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 1), ("", 1), ("abc", 1), ("0", 1), ("-3", 1), ("4", 4)],
)
def test_the_page_a_request_asks_for(value, expected):
    assert page_number(value) == expected


def test_a_short_list_has_no_pager():
    html = _render(3, 1)

    assert html.count('<li class="item">') == 3
    assert "pagination" not in html
    assert 'data-citations-url="/records/t5wk7-bsp06/citations"' in html


def test_a_page_of_a_long_list_is_numbered_from_its_first_citation():
    html = _render(462, 3)

    assert html.count('<li class="item">') == 25
    assert "Work 51." in html and "Work 75." in html
    assert "Work 50." not in html and "Work 76." not in html
    assert 'style="counter-reset: ordered 50"' in html
    assert "wide-numbers" not in html
    assert "51–75 of 462" in html


def test_the_pager_links_the_first_last_and_nearby_pages():
    html = _render(462, 10)

    assert 'class="active item"' in html
    assert 'data-citations-page="10" aria-current="page"' in html
    for page in (1, 8, 9, 11, 12, 19):
        assert f'data-citations-page="{page}"' in html
    for page in (2, 7, 13, 18):
        assert f'data-citations-page="{page}"' not in html
    assert html.count("…") == 2
    # Numbered 226 to 250: three digits.
    assert 'class="ui ordered list details-list wide-numbers"' in html
    assert 'href="?citations_page=11#citations"' in html


@pytest.mark.parametrize(("page", "shown"), [(0, "1–25"), (99, "451–462")])
def test_a_page_out_of_range_shows_the_nearest(page, shown):
    assert f"{shown} of 462" in _render(462, page)


def test_the_first_page_disables_previous_and_the_last_next():
    first = _render(60, 1)
    last = _render(60, 3)

    assert '<span class="disabled item">‹</span>' in first
    assert '<span class="disabled item">›</span>' in last
    assert "Work 60." in last


def test_the_record_page_shows_a_page_and_fetches_the_others():
    template = (
        ROOT / "templates/semantic-ui/invenio_app_rdm/records/details/details.html"
    ).read_text()

    assert 'id="citations"' in template
    assert 'request.args.get("citations_page")' in template
    assert "starter_citations_page(" in template
    assert "data-citations-url" in template and "a[data-citations-page]" in template


def test_the_citations_route_and_setting():
    from invenio_rdm_starter import config

    assert config.STARTER_CITATIONS_PAGE_SIZE == 25
    views = (ROOT / "site/invenio_rdm_starter/views.py").read_text()
    assert '"/records/<pid_value>/citations"' in views


@pytest.fixture()
def store_pages(monkeypatch):
    """The store's pages of citations, past those a record stores."""
    asked = []

    def _page(path, doi, page, size, current=None):
        asked.append((path, doi, page, size))
        first = (page - 1) * size
        return _citations(20746)[first : first + size], 20746

    monkeypatch.setattr(starter_citations, "citation_page", _page)
    return asked


def test_a_page_of_the_stored_citations_is_not_read_from_the_store(store_pages):
    html = _render(20746, 2, stored=1000)

    assert "Work 26." in html and "26–50 of 20746" in html
    assert store_pages == []


def test_a_page_past_the_stored_citations_is_read_from_the_store(store_pages):
    html = _render(20746, 41, stored=1000)

    assert store_pages == [("/store.sqlite3", "10.5555/cited", 41, 25)]
    assert "Work 1001." in html and "1001–1025 of 20746" in html
    assert 'data-citations-page="830"' in html  # the last page


def test_a_page_the_store_cannot_answer_says_so(monkeypatch):
    monkeypatch.setattr(starter_citations, "citation_page", lambda *a: None)

    html = _render(20746, 41, stored=1000)

    assert "could not be read just now" in html
    assert 'data-citations-page="42"' in html


@pytest.mark.parametrize(
    ("fields", "count"),
    [
        ({}, 0),
        (None, 0),
        ({"pidbox:citations": _citations(3)}, 3),
        ({"pidbox:citations": _citations(3), "pidbox:citation_count": 20746}, 20746),
        ({"pidbox:citations": _citations(3), "pidbox:citation_count": 1}, 3),
    ],
)
def test_the_citation_count_counts_those_not_stored(fields, count):
    assert citation_count(fields) == count
