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


COMMUNITIES_SUBTITLE = (
    "Organize, curate and collaborate on records for your institution, journal, "
    "repository, blog or event."
)


def test_the_communities_page_names_the_starters_community_types():
    """The Starter's copy of invenio-communities' communities page."""
    from pathlib import Path

    template = (
        Path(__file__).parents[3]
        / "templates/semantic-ui/invenio_communities/frontpage.html"
    ).read_text()

    assert f"{{{{_('{COMMUNITIES_SUBTITLE}')}}}}" in template
    assert (
        "{{_('Organize, curate and collaborate on records for your institution, project"
        not in template
    )


@pytest.mark.parametrize(
    ("locale", "start"),
    [
        ("de", "Organisieren, kuratieren"),
        ("es", "Organice, seleccione"),
        ("fr", "Organisez, gérez"),
        ("pt", "Organize, faça a curadoria"),
    ],
)
def test_the_communities_subtitle_is_translated(locale, start):
    catalog = Translations.load(str(TRANSLATIONS), [locale])

    assert catalog.gettext(COMMUNITIES_SUBTITLE).startswith(start)
