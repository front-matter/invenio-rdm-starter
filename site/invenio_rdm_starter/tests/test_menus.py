"""Tests for the Starter's menubar."""

from importlib.metadata import entry_points

from flask import Flask
from flask_menu import Menu, current_menu
from invenio_rdm_starter.menus import finalize_app, remove_menu_items


def _app_with_invenio_menus() -> Flask:
    """An app with the menu items InvenioRDM registers, and two to keep."""
    app = Flask(__name__)
    Menu(app)

    @app.route("/")
    def index():
        return "ok"

    with app.app_context():
        current_menu.submenu("actions.deposit").register("index", "My dashboard")
        current_menu.submenu("notifications.requests").register("index", "Requests")
        current_menu.submenu("plus.deposit").register("index", "New upload")
        current_menu.submenu("plus.community").register("index", "New community")
    return app


def _menu(app: Flask, path: str) -> list[str]:
    with app.app_context():
        return [child.name for child in current_menu.submenu(path).children]


def test_the_inbox_and_the_plus_menu_are_removed():
    app = _app_with_invenio_menus()

    with app.app_context():
        removed = remove_menu_items()

    assert removed == ["notifications.requests", "plus.deposit", "plus.community"]
    assert _menu(app, "notifications") == []
    # Removed, not hidden: the header shows "+" while plus has any items.
    assert _menu(app, "plus") == []
    assert _menu(app, "actions") == ["deposit"]


def test_a_missing_item_is_left_alone():
    app = Flask(__name__)
    Menu(app)

    with app.app_context():
        assert remove_menu_items() == []


def test_the_items_go_on_the_first_request_after_every_hook_ran():
    """The finalize hook can run before the hooks that register the items."""
    app = Flask(__name__)
    Menu(app)

    @app.route("/")
    def index():
        return "ok"

    with app.app_context():
        finalize_app(app)
        # Registered after the Starter's hook, as invenio-app-rdm's may be.
        current_menu.submenu("plus.deposit").register("index", "New upload")

    app.test_client().get("/")

    assert _menu(app, "plus") == []


def test_an_app_without_menus_is_left_alone():
    """The REST API app runs the same hooks and has no menus."""
    app = Flask(__name__)

    @app.route("/")
    def index():
        return "ok"

    finalize_app(app)

    assert app.test_client().get("/").status_code == 200


def test_the_hook_is_registered():
    registered = {
        ep.name: ep.value for ep in entry_points(group="invenio_base.finalize_app")
    }

    assert registered.get("invenio_rdm_starter_menus") == (
        "invenio_rdm_starter.menus:finalize_app"
    )
