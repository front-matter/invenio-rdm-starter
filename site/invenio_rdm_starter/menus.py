"""The Starter's menubar: without the inbox and the "+" menu.

InvenioRDM registers both as menu items when the app is finalized: the
inbox as ``notifications.requests`` (invenio-app-rdm), the "+" menu as the
items of ``plus``, a new upload (invenio-app-rdm) and a new community
(invenio-communities). The Starter's records are imported, not deposited,
and nobody reviews them, so neither leads anywhere a reader of the Starter
goes. Uploads stay reachable from "My dashboard".

The items are removed rather than hidden: the header shows the "+" button
whenever ``plus`` has items at all, visible or not. And they are removed on
the first request rather than in the finalize hook itself: invenio-base runs
the finalize hooks in the order the packages' entry points are found, so the
Starter's can come before the ones that register the items.
"""

from __future__ import annotations

import structlog
from flask import Flask
from flask_menu import current_menu

#: The menu items the Starter's menubar leaves out.
REMOVED_MENU_ITEMS = (
    "notifications.requests",
    "plus.deposit",
    "plus.community",
)


def remove_menu_items(paths: tuple[str, ...] = REMOVED_MENU_ITEMS) -> list[str]:
    """Remove menu items by their path, and return the paths it removed.

    Flask-Menu has no public way to remove an item, only to hide one, so this
    takes the item out of its parent's entries. A path that isn't there, as
    when a package no longer registers it, is left alone.
    """
    removed = []
    for path in paths:
        node = current_menu.submenu(path, auto_create=False)
        if node is None or node.parent is None:
            continue
        node.parent._child_entries.pop(node.name, None)
        removed.append(path)
    return removed


def finalize_app(app: Flask) -> None:
    """Remove the inbox and the "+" menu before the first request is served.

    Loaded through the ``invenio_base.finalize_app`` entry point
    ``invenio_rdm_starter_menus``.
    """
    # The REST API app has no menus, and runs the same finalize hooks.
    if "menu" not in app.extensions:
        return
    log = structlog.get_logger().bind(service="invenio-rdm-starter")
    state = {"done": False}

    @app.before_request
    def _remove_menu_items_once() -> None:
        if state["done"]:
            return
        state["done"] = True
        log.info("menu_items_removed", paths=remove_menu_items())
