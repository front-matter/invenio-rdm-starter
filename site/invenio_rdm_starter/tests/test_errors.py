"""Tests for unmasking KeyErrors in the records UI."""

from importlib.metadata import entry_points

import pytest
from flask import Blueprint, Flask
from invenio_rdm_starter.errors import (
    RECORDS_UI_BLUEPRINT,
    finalize_app,
    unmask_key_errors,
)


class RecordGone(Exception):
    """Stands in for the not-found errors invenio-app-rdm keeps handling."""


def _app() -> Flask:
    """An app with a records UI blueprint shaped like invenio-app-rdm's."""
    app = Flask("invenio")
    blueprint = Blueprint(RECORDS_UI_BLUEPRINT, __name__)

    @blueprint.route("/records/<pid_value>")
    def record_detail(pid_value: str):
        if pid_value == "gone":
            raise RecordGone(pid_value)
        sort_options = {"newest": {}}
        return sort_options["newestactivity"]

    def not_found(error: Exception):
        return "Page not found", 404

    blueprint.register_error_handler(KeyError, not_found)
    blueprint.register_error_handler(RecordGone, not_found)
    app.register_blueprint(blueprint)
    return app


def test_a_key_error_is_a_404_before():
    """What invenio-app-rdm does: the bug reads as a missing record."""
    response = _app().test_client().get("/records/xrf3z-d8y44")

    assert response.status_code == 404


def test_a_key_error_is_a_500_after():
    app = _app()

    assert unmask_key_errors(app) is True
    response = app.test_client().get("/records/xrf3z-d8y44")

    assert response.status_code == 500


def test_a_key_error_reaches_the_error_log():
    """Unhandled, it goes through Flask's logging, and so to Sentry."""
    app = _app()
    app.config["PROPAGATE_EXCEPTIONS"] = True
    unmask_key_errors(app)

    with pytest.raises(KeyError, match="newestactivity"):
        app.test_client().get("/records/xrf3z-d8y44")


def test_a_missing_record_is_still_a_404():
    app = _app()
    finalize_app(app)

    response = app.test_client().get("/records/gone")

    assert response.status_code == 404


def test_nothing_to_remove_is_not_an_error():
    """Once fixed upstream there is no handler left to remove."""
    app = _app()
    unmask_key_errors(app)

    assert unmask_key_errors(app) is False


def test_the_entry_point_is_registered():
    names = {ep.name for ep in entry_points(group="invenio_base.finalize_app")}

    assert "invenio_rdm_starter" in names
