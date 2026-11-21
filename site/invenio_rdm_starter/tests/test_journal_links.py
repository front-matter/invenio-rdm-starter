"""The record page links a journal to its container page."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parents[3] / "templates" / "semantic-ui"
JOURNAL = {"title": "mBio", "issue": "11", "volume": "17", "issn": "2150-7511"}
LINK = '<a href="/containers/2150-7511">2150-7511</a>'
TITLE_LINK = '<a class="display-inline" href="/containers/2150-7511">mBio</a>'


def _environment() -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
        extensions=["jinja2.ext.do"],
    )
    environment.globals["_"] = lambda text, **kwargs: text
    # Invenio's own filters, which the record page's macros name, as
    # stand-ins: none of them is used on the way to "Published in".
    macros = (TEMPLATES / "invenio_app_rdm/records/macros/detail.html").read_text()
    for name in re.findall(r"\|\s*(\w+)", macros):
        environment.filters.setdefault(name, lambda value, *args, **kwargs: value)
    environment.globals["url_for"] = (
        lambda endpoint, **kwargs: f"/containers/{kwargs['issn']}"
    )
    return environment


def _sidebar(
    containers: bool, journal: str, issn: str | None, title: str | None = "mBio"
) -> str:
    template = _environment().get_template(
        "invenio_app_rdm/records/details/side_bar/details.html"
    )
    field = {key: value for key, value in (("issn", issn), ("title", title)) if value}
    return template.render(
        config={"PIDBOX_CONTAINER_PROFILES": containers},
        metadata={},
        record_ui={
            "ui": {
                "publishing_information": {"journal": journal},
                "resource_type": None,
                "conference": None,
                "languages": None,
            },
            "custom_fields": {"journal:journal": field} if field else {},
        },
    )


PUBLISHED_IN = "mBio, 17(11), ISSN: 2150-7511, 2026."


def test_published_in_links_the_title_not_the_issn():
    html = _sidebar(True, PUBLISHED_IN, "2150-7511")

    assert f"{TITLE_LINK}, 17(11), ISSN: 2150-7511, 2026." in html


def test_published_in_escapes_the_rest_of_the_text():
    html = _sidebar(
        True, "A & B <i>Letters</i>, ISSN: 2150-7511.", "2150-7511", "A & B"
    )

    link = '<a class="display-inline" href="/containers/2150-7511">A &amp; B</a>'
    assert f"{link} &lt;i&gt;Letters&lt;/i&gt;, ISSN: 2150-7511." in html


def test_only_the_first_mention_of_the_title_is_linked():
    html = _sidebar(True, "Data, 3(1), ISSN: 2150-7511, Data.", "2150-7511", "Data")

    assert html.count("/containers/2150-7511") == 1


@pytest.mark.parametrize(
    ("containers", "issn", "title"),
    [
        (False, "2150-7511", "mBio"),  # container pages off
        (True, None, "mBio"),  # no ISSN to link to
        (True, "2150-7511", None),  # no title to link
        (True, "2150-7511", "Another journal"),  # title not in the sentence
    ],
)
def test_published_in_stays_text(containers, issn, title):
    html = _sidebar(containers, PUBLISHED_IN, issn, title)

    assert PUBLISHED_IN in html
    assert "/containers/" not in html


@pytest.mark.parametrize("containers", [True, False])
def test_the_journal_section_links_the_issn(containers):
    template = _environment().get_template("journal.html")

    html = template.render(
        field_value=JOURNAL, config={"PIDBOX_CONTAINER_PROFILES": containers}
    )

    assert (LINK in html) is containers
    assert "2150-7511" in html
    assert "<dd>mBio</dd>" in html
