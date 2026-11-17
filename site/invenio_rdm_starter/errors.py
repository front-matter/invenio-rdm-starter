"""Error handling the Starter changes in InvenioRDM.

invenio-app-rdm registers ``not_found_error`` for every ``KeyError`` raised in
the views of its records UI blueprint (``invenio_app_rdm_records``: landing
pages, files, previews, the deposit form). A missing dictionary key is almost
always a bug or a configuration error, not a missing record, and turning it
into "Page not found" hides it: nothing is logged, Sentry hears nothing, and
the page reads as a record that does not exist. That is how a missing
``newestactivity`` in ``RDM_SORT_OPTIONS`` made every landing page a 404.

The genuine not-found cases keep their own handlers in invenio-app-rdm
(``PIDDoesNotExistError``, ``PIDUnregistered``, ``NoResultFound``,
``FileKeyNotFoundError``), and none of them is a ``KeyError``. Without the
``KeyError`` handler a ``KeyError`` takes Flask's path for unhandled errors:
logged with its traceback, reported to Sentry, and answered with the 500 page.

Upstream: inveniosoftware/invenio-app-rdm#3559 (issue) and #3590 (pull request,
removing the same handler). Once that is released, there is no handler left
here to remove and :func:`unmask_key_errors` does nothing.
"""

import structlog
from flask import Flask

#: The blueprint of invenio-app-rdm's records UI.
RECORDS_UI_BLUEPRINT = "invenio_app_rdm_records"


def unmask_key_errors(app: Flask, blueprint: str = RECORDS_UI_BLUEPRINT) -> bool:
    """Remove the blueprint's handler that answers a ``KeyError`` with a 404.

    Returns whether a handler was removed. Flask keeps a blueprint's error
    handlers in ``app.error_handler_spec[<blueprint>][<code>]``, keyed by
    exception class; a class handler is registered under the code ``None``.
    """
    log = structlog.get_logger().bind(service="invenio-rdm-starter")
    handlers = app.error_handler_spec.get(blueprint, {}).get(None, {})
    if handlers.pop(KeyError, None) is None:
        # Fixed upstream, or the blueprint was renamed: nothing to undo.
        log.debug("no KeyError handler to remove", blueprint=blueprint)
        return False
    log.debug("KeyError handler removed", blueprint=blueprint)
    return True


def finalize_app(app: Flask) -> None:
    """Adjust InvenioRDM's error handling once every blueprint is registered.

    Loaded through the ``invenio_base.finalize_app`` entry point
    ``invenio_rdm_starter``, which invenio-base runs after the blueprints.
    """
    unmask_key_errors(app)
