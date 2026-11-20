"""Whether there are records, for the front page."""

from __future__ import annotations

import sys
from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest
from flask import Flask
from invenio_rdm_starter import frontpage


class RecordsService:
    """The records service, answering searches with a total."""

    def __init__(self, total: int | None = None, error: Exception | None = None):
        self.total = total
        self.error = error
        self.searches = 0

    def search(self, identity, params):
        self.searches += 1
        if self.error:
            raise self.error
        return SimpleNamespace(total=self.total)


@pytest.fixture()
def records(monkeypatch):
    def _install(**kwargs) -> RecordsService:
        service = RecordsService(**kwargs)
        proxy = SimpleNamespace(records_service=service)
        monkeypatch.setitem(
            sys.modules,
            "invenio_rdm_records.proxies",
            SimpleNamespace(current_rdm_records=proxy),
        )
        return service

    return _install


@pytest.fixture()
def flask_app():
    """Not named ``app``: pytest-flask would wrap the test in a request of it,
    and its requests here would share one ``g``."""
    app = Flask(__name__)
    frontpage.finalize_app(app)
    return app


def test_the_total_is_searched_once_a_request(flask_app, records):
    service = records(total=0)

    with flask_app.test_request_context("/"):
        assert frontpage.records_total() == 0
        assert frontpage.records_total() == 0
    with flask_app.test_request_context("/"):
        assert flask_app.jinja_env.globals["starter_records_total"]() == 0

    assert service.searches == 2


def test_an_unknown_total_when_search_fails(flask_app, records):
    records(error=ConnectionError("search unreachable"))

    with flask_app.test_request_context("/"):
        assert frontpage.records_total() is None


def test_the_hook_is_registered():
    registered = {
        ep.name: ep.value for ep in entry_points(group="invenio_base.finalize_app")
    }

    assert registered.get("invenio_rdm_starter_frontpage") == (
        "invenio_rdm_starter.frontpage:finalize_app"
    )
