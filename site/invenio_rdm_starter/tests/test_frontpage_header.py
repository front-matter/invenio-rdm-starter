"""The front page header: the site's title and subtitle above pidbox's metrics."""

from __future__ import annotations

from pathlib import Path

import invenio_pidbox
import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

STARTER_TEMPLATES = Path(__file__).resolve().parents[3] / "templates" / "semantic-ui"
PIDBOX_TEMPLATES = Path(invenio_pidbox.__file__).parent / "templates" / "semantic-ui"

STUBS = {
    "header.html": "{% block navbar %}<nav></nav>{% endblock navbar %}",
    "invenio_app_rdm/frontpage_metrics.html": "<div id=metrics></div>",
}


def _render(**config: object) -> str:
    environment = Environment(
        loader=ChoiceLoader(
            [
                DictLoader(STUBS),
                FileSystemLoader(str(STARTER_TEMPLATES)),
                FileSystemLoader(str(PIDBOX_TEMPLATES)),
            ]
        )
    )
    environment.globals["_"] = lambda text: text
    settings = {
        "THEME_HEADER_TEMPLATE": "header.html",
        "THEME_FRONTPAGE_TITLE": "InvenioRDM Starter",
        "THEME_FRONTPAGE_SUBTITLE": "A starter project.",
        "PIDBOX_FRONTPAGE_METRICS": True,
        "PIDBOX_FRONTPAGE_METRICS_BACKGROUND": "#cbd5e1",
        **config,
    }
    template = environment.get_template("invenio_rdm_starter/header_frontpage.html")
    return template.render(config=settings)


def test_title_and_subtitle_sit_above_the_metrics() -> None:
    html = _render()

    assert html.index("InvenioRDM Starter") < html.index("<div id=metrics>")
    assert '<div class="sub header">A starter project.</div>' in html
    assert "inverted" not in html  # dark ink on the light band


@pytest.mark.parametrize(
    "config",
    [
        {"PIDBOX_FRONTPAGE_METRICS": False},
        {"PIDBOX_FRONTPAGE_METRICS_BACKGROUND": None},
    ],
)
def test_title_stays_white_on_the_theme_band(config: dict) -> None:
    html = _render(**config)

    assert "InvenioRDM Starter" in html
    assert "header inverted" in html


def test_no_title_row_without_a_title() -> None:
    html = _render(THEME_FRONTPAGE_TITLE="", THEME_FRONTPAGE_SUBTITLE="")

    assert "starter-frontpage-title" not in html
    assert "<div id=metrics>" in html
