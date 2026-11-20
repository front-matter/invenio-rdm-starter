"""The record page links a journal's ISSN to its container page."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parents[3] / "templates" / "semantic-ui"
JOURNAL = {"title": "mBio", "issue": "11", "volume": "17", "issn": "2150-7511"}
LINK = '<a href="/containers/2150-7511">2150-7511</a>'
INLINE_LINK = '<a class="display-inline" href="/containers/2150-7511">2150-7511</a>'


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


def _sidebar(containers: bool, journal: str, issn: str | None) -> str:
    template = _environment().get_template(
        "invenio_app_rdm/records/details/side_bar/details.html"
    )
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
            "custom_fields": {"journal:journal": {"issn": issn}} if issn else {},
        },
    )


def test_published_in_links_the_issn():
    html = _sidebar(True, "mBio, 17(11), ISSN: 2150-7511, 2026.", "2150-7511")

    assert f"mBio, 17(11), ISSN: {INLINE_LINK}, 2026." in html


def test_published_in_escapes_the_rest_of_the_text():
    html = _sidebar(True, "<b>A & B</b>, ISSN: 2150-7511.", "2150-7511")

    assert f"&lt;b&gt;A &amp; B&lt;/b&gt;, ISSN: {INLINE_LINK}." in html


@pytest.mark.parametrize(("containers", "issn"), [(False, "2150-7511"), (True, None)])
def test_published_in_stays_text(containers, issn):
    html = _sidebar(containers, "mBio, 17(11), ISSN: 2150-7511, 2026.", issn)

    assert "mBio, 17(11), ISSN: 2150-7511, 2026." in html
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
