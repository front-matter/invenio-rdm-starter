"""Tests for the Starter's own translations."""

from importlib.metadata import entry_points
from importlib.resources import files

import pytest
from babel.support import Translations

TRANSLATIONS = files("invenio_rdm_starter") / "translations"


def test_invenio_i18n_finds_the_translations():
    """invenio-i18n loads <module>/translations for each entry point."""
    modules = {ep.value for ep in entry_points(group="invenio_i18n.translations")}

    assert "invenio_rdm_starter" in modules
    assert TRANSLATIONS.is_dir()


@pytest.mark.parametrize(
    ("locale", "text"),
    [
        ("de", "Kürzlich veröffentlichte Werke"),
        ("es", "Obras publicadas recientemente"),
        ("fr", "Travaux récemment publiés"),
        ("pt", "Trabalhos publicados recentemente"),
    ],
)
def test_the_front_page_list_title_is_translated(locale, text):
    """Read from the compiled catalog, so a .po edited without compiling fails."""
    catalog = Translations.load(str(TRANSLATIONS), [locale])

    assert catalog.gettext("Recently published works") == text

