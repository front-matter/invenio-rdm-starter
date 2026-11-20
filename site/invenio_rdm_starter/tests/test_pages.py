"""The front page's pages, read in the current language or the default."""

from __future__ import annotations

from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest
from flask import Flask
from flask_babel import Babel, force_locale
from invenio_pages.records.errors import PageNotFoundError
from invenio_rdm_starter import pages


class PagesService:
    """The pages in the database, by URL and language."""

    def __init__(self, stored: dict[tuple[str, str], dict]) -> None:
        self.stored = stored
        self.reads: list[tuple[str, str]] = []

    def read_by_url(self, identity, url, lang):
        self.reads.append((url, lang))
        if (url, lang) not in self.stored:
            raise PageNotFoundError(url)
        page = self.stored[(url, lang)]
        return SimpleNamespace(to_dict=lambda: page)


@pytest.fixture()
def app():
    app = Flask(__name__)
    app.config["BABEL_DEFAULT_LOCALE"] = "en"
    Babel(app)
    pages.finalize_app(app)
    with app.test_request_context("/"):
        yield app


def _with(monkeypatch, stored) -> PagesService:
    service = PagesService(stored)
    monkeypatch.setattr(pages, "current_pages_service", service)
    return service


def test_the_page_in_the_current_language(app, monkeypatch):
    _with(monkeypatch, {("/about", "de"): {"title": "Über"}, ("/about", "en"): {}})

    with force_locale("de"):
        assert pages.read_page("/about") == {"title": "Über"}


def test_the_default_language_when_the_current_one_has_none(app, monkeypatch):
    service = _with(monkeypatch, {("/about", "en"): {"title": "About"}})

    with force_locale("fr"):
        assert pages.read_page("/about") == {"title": "About"}
    assert service.reads == [("/about", "fr"), ("/about", "en")]


@pytest.mark.parametrize("url", ["/missing", None, ""])
def test_no_page(app, monkeypatch, url):
    _with(monkeypatch, {})

    assert pages.read_page(url) is None


def test_templates_read_pages(app, monkeypatch):
    _with(monkeypatch, {("/about", "en"): {"title": "About"}})

    assert app.jinja_env.globals["starter_page"]("/about") == {"title": "About"}


def test_the_hook_is_registered():
    registered = {
        ep.name: ep.value for ep in entry_points(group="invenio_base.finalize_app")
    }

    assert registered.get("invenio_rdm_starter_pages") == (
        "invenio_rdm_starter.pages:finalize_app"
    )
