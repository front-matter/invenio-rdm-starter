"""Tests for a record's citations, a page at a time."""

from pathlib import Path

import pytest
from flask import Flask
from invenio_rdm_starter import citations as starter_citations
from invenio_rdm_starter.citations import citation_count, citations_page, page_number
from jinja2 import ChoiceLoader, FileSystemLoader

ROOT = Path(__file__).parents[3]


def _sanitize_html(value: str, **kwargs) -> str:
    """invenio-formatter's filter, which, as bleach, takes text only."""
    if not isinstance(value, str):
        raise TypeError(f"argument cannot be of {type(value).__name__!r} type")
    return value


def _app() -> Flask:
    app = Flask(__name__)
    app.config["STARTER_CITATIONS_PAGE_SIZE"] = 25
    app.config["PIDBOX_SQLITE_PATH"] = "/store.sqlite3"
    app.jinja_loader = ChoiceLoader(
        [FileSystemLoader(str(ROOT / "templates/semantic-ui"))]
    )
    app.jinja_env.globals["_"] = lambda text, **kwargs: text % kwargs
    app.jinja_env.filters["sanitize_html"] = _sanitize_html
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
    app.add_url_rule(
        "/records/<pid_value>/references",
        endpoint="invenio_rdm_starter.record_references",
    )
    app.add_url_rule("/search", endpoint="invenio_search_ui.search")
    app.add_url_rule(
        "/communities/<pid_value>/records",
        endpoint="invenio_app_rdm_communities.communities_detail",
    )
    return app


def _citations(count: int, formatted: bool = True) -> list[dict]:
    return [
        {
            "identifier": f"10.5555/{n}",
            "scheme": "doi",
            "reference": f"Work {n}." if formatted else None,
            "publication_year": 2024,
        }
        for n in range(1, count + 1)
    ]


class FakeGraph:
    """invenio-pidbox's citations kept in Postgres, for one cited DOI."""

    def __init__(self, count: int, formatted: bool = True):
        self.entries = _citations(count, formatted)
        self.read: list[tuple] = []

    def read_references(self, references, style=None, locale=None):
        self.locale = locale
        return [
            (
                dict(entry, reference=f"Rendered {entry['identifier']}.")
                if entry.get("identifier") == "10.5555/read"
                else dict(entry)
            )
            for entry in references
        ]

    def count_citations(self, doi):
        return len(self.entries) if doi == "10.5555/cited" else 0

    def read_citations(self, doi, page=1, size=25, style=None, locale=None):
        self.read.append((doi, page, size))
        self.locale = locale
        first = (page - 1) * size
        return self.entries[first : first + size], len(self.entries)


@pytest.fixture()
def kept(monkeypatch):
    """Keep ``count`` citations for the cited DOI; returns the fake."""

    def _keep(count: int, formatted: bool = True) -> FakeGraph:
        fake = FakeGraph(count, formatted)
        monkeypatch.setattr(starter_citations, "graph", fake)
        return fake

    return _keep


def _render(page: int, size: int = 25, doi: str = "10.5555/cited") -> str:
    app = _app()
    with app.test_request_context():
        return app.jinja_env.get_template("invenio_rdm_starter/citations.html").render(
            citations=citations_page(doi, page, size),
            record_id="t5wk7-bsp06",
            community_slug=None,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 1), ("", 1), ("abc", 1), ("0", 1), ("-3", 1), ("4", 4)],
)
def test_the_page_a_request_asks_for(value, expected):
    assert page_number(value) == expected


def test_a_short_list_has_no_pager(kept):
    kept(3)
    html = _render(1)

    assert html.count('<li class="item">') == 3
    assert "pagination" not in html
    assert 'data-citations-url="/records/t5wk7-bsp06/citations"' in html


def test_a_page_of_a_long_list_is_numbered_from_its_first_citation(kept):
    fake = kept(462)
    html = _render(3)

    assert html.count('<li class="item">') == 25
    assert "Work 51." in html and "Work 75." in html
    assert "Work 50." not in html and "Work 76." not in html
    assert 'style="counter-reset: ordered 50"' in html
    assert "wide-numbers" not in html
    assert "51–75 of 462" in html
    # Only the page is read.
    assert fake.read == [("10.5555/cited", 3, 25)]


def test_the_pager_links_the_first_last_and_nearby_pages(kept):
    kept(462)
    html = _render(10)

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
def test_a_page_out_of_range_shows_the_nearest(kept, page, shown):
    kept(462)
    assert f"{shown} of 462" in _render(page)


def test_the_first_page_disables_previous_and_the_last_next(kept):
    kept(60)
    first = _render(1)
    last = _render(3)

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
    # The script swaps a page of either list in, by its data attributes.
    assert '"[data-" + kind + "-url]"' in template
    assert '"a[data-" + kind + "-page]"' in template


def test_the_citations_route_and_setting():
    from invenio_rdm_starter import config

    assert config.STARTER_CITATIONS_PAGE_SIZE == 25
    views = (ROOT / "site/invenio_rdm_starter/views.py").read_text()
    assert '"/records/<pid_value>/citations"' in views


def test_a_citation_not_formatted_yet_is_shown_by_its_doi(kept):
    kept(1, formatted=False)

    html = _render(1)

    assert 'href="https://doi.org/10.5555/1"' in html
    assert "creatibutor-link" not in html


def test_a_page_of_a_doi_cited_tens_of_thousands_of_times(kept):
    fake = kept(20746)

    html = _render(41)

    assert fake.read == [("10.5555/cited", 41, 25)]
    assert "Work 1001." in html and "1001–1025 of 20746" in html
    assert 'data-citations-page="830"' in html  # the last page


def test_a_record_without_citations_has_none(kept):
    kept(5)

    page = None
    app = _app()
    with app.app_context():
        page = citations_page("10.5555/other", 1, 25)

    assert page["total"] == 0 and page["entries"] == []


@pytest.mark.parametrize(("doi", "count"), [(None, 0), ("", 0), ("10.5555/cited", 3)])
def test_the_citation_count_is_that_of_the_kept_citations(kept, doi, count):
    kept(3)

    assert citation_count(doi) == count


def _references(count: int) -> list[dict]:
    return [
        {"reference": f"Deposited {n}.", "scheme": "doi", "identifier": f"10.5555/{n}"}
        for n in range(1, count + 1)
    ]


def _render_references(references, page: int, size: int = 25) -> str:
    from invenio_rdm_starter.citations import references_page

    app = _app()
    with app.test_request_context():
        return app.jinja_env.get_template("invenio_rdm_starter/references.html").render(
            references=references_page(references, page, size),
            record_id="t5wk7-bsp06",
            community_slug=None,
        )


def test_a_page_of_references_in_their_order(kept):
    kept(0)

    html = _render_references(_references(60), 2)

    assert "Deposited 26." in html and "Deposited 50." in html
    assert "Deposited 25." not in html and "Deposited 51." not in html
    assert "26–50 of 60" in html
    assert 'data-references-url="/records/t5wk7-bsp06/references"' in html
    assert 'href="?references_page=3#references"' in html
    assert 'data-references-page="3"' in html


def test_a_reference_whose_work_is_read_is_rendered(kept):
    kept(0)
    references = [
        {"reference": "Deposited.", "scheme": "doi", "identifier": "10.5555/read"},
        {"reference": "A book."},
    ]

    html = _render_references(references, 1)

    assert "Rendered 10.5555/read." in html and "Deposited." not in html
    assert "A book." in html
    assert "pagination" not in html


def test_the_record_page_pages_its_references():
    template = (
        ROOT / "templates/semantic-ui/invenio_app_rdm/records/details/details.html"
    ).read_text()

    assert 'id="references"' in template
    assert (
        'starter_references_page(metadata.references, request.args.get("references_page"))'
        in template
    )
    assert '["references", "citations"].forEach' in template
