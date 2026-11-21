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

"My profile" (``settings.person``) follows it for a user with an ORCID iD,
which a login through ORCID, or a provider that sends an orcid claim, links
to the account (``invenio_rdm_starter.oidc``): it leads to the user's person
page, ``/people/<orcid>``, while invenio-pidbox's person pages are on.

"Communities" (``main.communities``, invenio-communities) becomes "Starter
Packs": the communities search for the Starter Packs' communities
(``/communities-search?q=&f=type:starterpack``), the Starter's own.

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
from flask_login import current_user
from flask_menu import current_menu

#: The menu items the Starter's menubar leaves out.
REMOVED_MENU_ITEMS = (
    "notifications.requests",
    "plus.deposit",
    "plus.community",
    "actions.deposit",
)

#: "Starter Packs" in the menubar, in place of "Communities": the
#: communities search, for the communities of type Starter Pack.
STARTER_PACKS_MENU_ITEM = "main.communities"
STARTER_PACKS_ENDPOINT = "invenio_communities.communities_search"
STARTER_PACKS_SEARCH = {"q": "", "f": "type:starterpack"}

#: "My dashboard" in the user menu: its path, invenio-app-rdm's endpoint, and
#: an order between "Profile" (0) and "Change password" (1).
DASHBOARD_MENU_ITEM = "settings.dashboard"
DASHBOARD_ENDPOINT = "invenio_app_rdm_users.uploads"
DASHBOARD_ORDER = 0.5


#: "My profile" in the user menu: the user's person page, after "My dashboard".
PERSON_MENU_ITEM = "settings.person"
PERSON_ENDPOINT = "invenio_pidbox.person_profile"
PERSON_ORDER = 0.75


def user_orcid() -> str | None:
    """The logged-in user's ORCID iD, or ``None``.

    Read from the identities linked to the account (``UserIdentity``, method
    ``orcid``), which invenio-accounts loads with the user.
    """
    if not (current_user and current_user.is_authenticated):
        return None
    for identity in getattr(current_user, "external_identifiers", None) or []:
        if identity.method == "orcid" and identity.id:
            return identity.id
    return None


def _person_page_visible() -> bool:
    return bool(current_app.config.get("PIDBOX_PERSON_PROFILES")) and bool(user_orcid())


def _person_text() -> str:
    # The icon of the person pages' ORCID iD; "My profile" as invenio-app-rdm
    # doesn't say it, so it's translated in the Starter.
    return f'<i class="user circle icon"></i> {gettext("My profile")}'


def add_person_page_to_user_menu() -> str | None:
    """Add "My profile", the user's person page, to the user menu.

    Shown only to a user with an ORCID iD while invenio-pidbox's person pages
    are on. Left out, returning ``None``, when invenio-pidbox isn't routed in
    this app.
    """
    if PERSON_ENDPOINT not in current_app.view_functions:
        return None
    current_menu.submenu(PERSON_MENU_ITEM).register(
        endpoint=PERSON_ENDPOINT,
        text=LazyString(_person_text),
        order=PERSON_ORDER,
        endpoint_arguments_constructor=lambda: {"orcid": user_orcid()},
        visible_when=_person_page_visible,
    )
    return PERSON_MENU_ITEM


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


def _starter_packs_text() -> str:
    # The Starter's catalogs translate "Starter Packs".
    return gettext("Starter Packs")


def link_starter_packs_in_menubar() -> str | None:
    """Make "Communities" in the menubar "Starter Packs", and return its path.

    Left as it is, returning ``None``, when the communities search isn't
    routed in this app.
    """
    if STARTER_PACKS_ENDPOINT not in current_app.view_functions:
        return None
    current_menu.submenu(STARTER_PACKS_MENU_ITEM).register(
        endpoint=STARTER_PACKS_ENDPOINT,
        text=LazyString(_starter_packs_text),
        order=1,
        endpoint_arguments_constructor=lambda: dict(STARTER_PACKS_SEARCH),
    )
    return STARTER_PACKS_MENU_ITEM


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

    Removes the inbox, the "+" menu and "My dashboard" from the menubar, adds
    "My dashboard" and "My profile" to the user menu, and makes "Communities"
    "Starter Packs".

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
        log.info("menu_item_added", path=add_person_page_to_user_menu())
        log.info("menu_item_changed", path=link_starter_packs_in_menubar())
