"""What the front page needs to know about the records: whether there are any.

A demo instance starts afresh with no records ("Delete all records"), and
until the imports run, the front page's metrics band would be empty and its
list of works blank. The front page asks ``starter_records_total()``, and
with no records shows the plain header and a message instead.
"""

from __future__ import annotations

import structlog
from flask import Flask, g
from invenio_access.permissions import system_identity

_CACHE = "_starter_records_total"


def records_total() -> int | None:
    """How many published records there are, once per request.

    ``None`` when the search can't say, so that the front page shows what it
    always does.
    """
    if hasattr(g, _CACHE):
        return getattr(g, _CACHE)
    total: int | None
    try:
        from invenio_rdm_records.proxies import current_rdm_records

        total = current_rdm_records.records_service.search(
            system_identity, params={"size": 1}
        ).total
    except Exception as error:  # noqa: BLE001 - the page renders all the same
        structlog.get_logger().bind(service="invenio-rdm-starter").warning(
            "records_total_unavailable", error=str(error)
        )
        total = None
    setattr(g, _CACHE, total)
    return total


def finalize_app(app: Flask) -> None:
    """Make ``starter_records_total`` a template global.

    Loaded through the ``invenio_base.finalize_app`` entry point
    ``invenio_rdm_starter_frontpage``.
    """
    app.add_template_global(records_total, "starter_records_total")
