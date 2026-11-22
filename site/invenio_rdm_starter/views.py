"""Additional views."""

import os
from functools import wraps
from pathlib import Path

from flask import Blueprint, abort, current_app, request
from invenio_administration.permissions import administration_permission
from prometheus_flask_exporter.multiprocess import (
    GunicornPrometheusMetrics,
    GunicornInternalPrometheusMetrics,
)

from .citations import record_citations
from .exceptions import ConfigNotLoadedError
from .filters import format_edtf_date

CONFIG_MODULE = "invenio_rdm_starter.config"


def require_config(app) -> None:
    """Refuse to start without the Starter's settings.

    They are loaded through the invenio_config.module entry point
    "invenio_rdm_starter". A package installed without it -- a venv not
    synced since the entry point was added -- would otherwise run the app on
    InvenioRDM's defaults without any error.
    """
    loaded = app.config.get("INVENIO_RDM_STARTER_CONFIG_MODULE")
    if loaded != CONFIG_MODULE:
        raise ConfigNotLoadedError(
            f"The InvenioRDM Starter's settings were not loaded (expected "
            f"{CONFIG_MODULE}, got {loaded!r}). Reinstall the package so its "
            f'invenio_config.module entry point "invenio_rdm_starter" is '
            f"registered, e.g. with `uv sync`."
        )


def _metrics_access(f):
    """Allow direct internal requests; require admin permission via proxy."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if request.headers.get("X-Forwarded-For"):
            # Request came through the upstream proxy — enforce auth
            if not administration_permission.can():
                abort(403)
        return f(*args, **kwargs)

    return decorated


def _init_metrics(app, **kwargs):
    """Initialize API metrics using Gunicorn multiprocess mode."""
    _ensure_multiproc_dir()
    return GunicornInternalPrometheusMetrics(app, **kwargs)


def _ensure_multiproc_dir():
    """Ensure Prometheus multiprocess directory exists and is configured."""
    multiproc_dir = (
        os.environ.get("PROMETHEUS_MULTIPROC_DIR")
        or os.environ.get("prometheus_multiproc_dir")
        or "/tmp/prometheus_multiproc"
    )
    os.environ.setdefault("PROMETHEUS_MULTIPROC_DIR", multiproc_dir)
    Path(multiproc_dir).mkdir(parents=True, exist_ok=True)
    return multiproc_dir


def _version():
    """Return the configured InvenioRDM version string."""
    return str(current_app.config.get("INVENIO_APP_RDM_VERSION", ""))


def create_api_blueprint(app):
    """Register Prometheus metrics on the API Flask app."""
    require_config(app)
    _init_metrics(
        app,
        path="/metrics",
        group_by="endpoint",
        metrics_decorator=_metrics_access,
    )
    # Disable HTTPS redirect for the metrics endpoint on the API app.
    # In the combined app this is exposed externally as /api/metrics.
    metrics_view = app.view_functions.get("prometheus_metrics")
    if metrics_view is not None:
        metrics_view.talisman_view_options = {"force_https": False}

    blueprint = Blueprint("invenio_rdm_starter_api", __name__)
    blueprint.add_url_rule("/version", endpoint="version", view_func=_version)

    return blueprint


#
# Registration
#
def create_blueprint(app):
    """Register blueprint routes on app."""
    require_config(app)
    # Track UI app requests in the shared multiprocess registry without
    # exposing an endpoint on the UI app.
    _ensure_multiproc_dir()
    GunicornPrometheusMetrics(app, group_by="endpoint", export_defaults=True)

    blueprint = Blueprint(
        "invenio_rdm_starter",
        __name__,
        template_folder="./templates",
    )
    blueprint.add_app_template_filter(format_edtf_date, "format_edtf")
    blueprint.add_url_rule(
        "/records/<pid_value>/citations",
        endpoint="record_citations",
        view_func=record_citations,
    )

    return blueprint
