"""Tests for the Starter's template filters."""

import pytest
from flask import Flask
from invenio_rdm_starter.filters import format_edtf_date
from invenio_rdm_starter.views import create_blueprint


@pytest.mark.parametrize(
    ("value", "locale", "formatted"),
    [
        pytest.param("2025-11-12", "en", "November 12, 2025", id="day"),
        pytest.param("2025-11-12", "de", "12. November 2025", id="day in German"),
        pytest.param("2025-11", "en", "November 2025", id="month"),
        pytest.param("2025", "en", "2025", id="year"),
        pytest.param("2020/2021", "de", "2020–2021", id="interval"),
        pytest.param("2025~", "en", "2025~", id="unsupported EDTF as stored"),
        pytest.param("not a date", "en", "not a date", id="not EDTF as stored"),
        pytest.param("", "en", "", id="empty"),
        pytest.param(None, "en", "", id="missing"),
    ],
)
def test_format_edtf_date(value, locale, formatted):
    assert format_edtf_date(value, locale=locale) == formatted


def test_the_filter_is_registered_for_templates(monkeypatch):
    """The dates section of the record page uses it as format_edtf."""
    monkeypatch.setattr("invenio_rdm_starter.views.require_config", lambda app: None)
    monkeypatch.setattr(
        "invenio_rdm_starter.views.GunicornPrometheusMetrics", lambda *a, **k: None
    )
    app = Flask(__name__)
    app.register_blueprint(create_blueprint(app))

    assert app.jinja_env.filters["format_edtf"] is format_edtf_date
