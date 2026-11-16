"""Tests for the guard against running without the Starter's settings."""

from importlib.metadata import entry_points

import pytest
from flask import Flask
from invenio_rdm_starter.exceptions import ConfigNotLoadedError
from invenio_rdm_starter.views import require_config


@pytest.mark.parametrize(
    "config",
    [
        pytest.param({}, id="not loaded"),
        pytest.param(
            {"INVENIO_RDM_STARTER_CONFIG_MODULE": "invenio_app_rdm.config"},
            id="another module",
        ),
    ],
)
def test_the_app_refuses_to_start_without_the_settings(config):
    app = Flask("invenio")
    app.config.update(config)

    with pytest.raises(ConfigNotLoadedError, match="uv sync"):
        require_config(app)


def test_the_app_starts_with_the_settings():
    app = Flask("invenio")
    app.config["INVENIO_RDM_STARTER_CONFIG_MODULE"] = "invenio_rdm_starter.config"

    require_config(app)


def test_the_entry_point_loads_after_invenio_app_rdm():
    """invenio-config loads entry points in alphabetical order of their names."""
    names = sorted(ep.name for ep in entry_points(group="invenio_config.module"))

    assert names.index("invenio_rdm_starter") > names.index("invenio_app_rdm")
