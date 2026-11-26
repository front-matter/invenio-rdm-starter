"""Tests for what the Starter shows of its own in a community's header."""

from pathlib import Path

import pytest
from flask import Flask
from jinja2 import FileSystemLoader

ROOT = Path(__file__).parents[3]
TEMPLATE = "invenio_communities/details/header_identifiers.html"


def _render(custom_fields: dict, **config) -> str:
    app = Flask(__name__)
    app.config.update(config)
    app.jinja_loader = FileSystemLoader(str(ROOT / "templates/semantic-ui"))
    with app.test_request_context():
        return app.jinja_env.get_template(TEMPLATE).render(
            community_ui={"custom_fields": custom_fields}, config=app.config
        )


def test_a_journal_shows_its_issn_linked_to_its_works():
    html = _render({"rs:issn": "2475-9066"})

    assert '<a href="/containers/2475-9066">ISSN 2475-9066</a>' in html
    assert "barcode icon" in html


def test_without_container_pages_the_issn_is_text():
    html = _render({"rs:issn": "2475-9066"}, PIDBOX_CONTAINER_PROFILES=False)

    assert "ISSN 2475-9066" in html
    assert "<a " not in html


@pytest.mark.parametrize("fields", [{}, {"rs:doi": "10.59350/rzepa"}])
def test_a_community_without_an_issn_shows_nothing(fields):
    assert _render(fields).strip() == ""
