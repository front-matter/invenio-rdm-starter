"""The Starter's menubar: without the inbox, the "+" menu and "My dashboard",
which moves into the user menu, below "Profile".

InvenioRDM registers both as menu items when the app is finalized: the
inbox as ``notifications.requests`` (invenio-app-rdm), the "+" menu as the
items of ``plus``, a new upload (invenio-app-rdm) and a new community
(invenio-communities). The Starter's records are imported, not deposited,
and nobody reviews them, so neither leads anywhere a reader of the Starter
goes. Uploads stay reachable from "My dashboard".

"My dashboard" (``actions.deposit``, invenio-app-rdm) sits in the menubar,
shown to everyone, and sends a visitor who isn't logged in to the login
page. The Starter shows it in the user menu instead (``settings.dashboard``),
which only a logged-in user has, second after "Profile" (``settings.profile``,
order 0; the next, "Change password", has order 1). The user menu is also the
sidebar of the account settings pages, so it shows there too.

The items are removed rather than hidden: the header shows the "+" button
whenever ``plus`` has items at all, visible or not. And they are removed on
the first request rather than in the finalize hook itself: invenio-base runs
the finalize hooks in the order the packages' entry points are found, so the
Starter's can come before the ones that register the items.
"""

from __future__ import annotations

import structlog
from flask import Flask, current_app
from flask_babel import LazyString, gettext
from flask_menu import current_menu

#: The menu items the Starter's menubar leaves out.
REMOVED_MENU_ITEMS = (
    "notifications.requests",
    "plus.deposit",
    "plus.community",
    "actions.deposit",
)

#: "My dashboard" in the user menu: its path, invenio-app-rdm's endpoint, and
#: an order between "Profile" (0) and "Change password" (1).
DASHBOARD_MENU_ITEM = "settings.dashboard"
DASHBOARD_ENDPOINT = "invenio_app_rdm_users.uploads"
DASHBOARD_ORDER = 0.5


def _dashboard_text() -> str:
    # invenio-app-rdm translates "My dashboard"; the icon is the user menu's
    # way, as "%(icon)s Profile" is.
    return f'<i class="tachometer alternate icon"></i> {gettext("My dashboard")}'


def add_dashboard_to_user_menu() -> str | None:
    """Add "My dashboard" to the user menu, and return its path.

    Left out, returning ``None``, when invenio-app-rdm's dashboard isn't
    routed in this app.
    """
    if DASHBOARD_ENDPOINT not in current_app.view_functions:
        return None
    current_menu.submenu(DASHBOARD_MENU_ITEM).register(
        endpoint=DASHBOARD_ENDPOINT,
        text=LazyString(_dashboard_text),
        order=DASHBOARD_ORDER,
    )
    return DASHBOARD_MENU_ITEM


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
    """Adjust the menubar before the first request is served.

    Removes the inbox, the "+" menu and "My dashboard" from the menubar, and
    adds "My dashboard" to the user menu.

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
        log.info("menu_item_added", path=add_dashboard_to_user_menu())
