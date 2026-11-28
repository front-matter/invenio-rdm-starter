"""Tests for a funder community's records search: its works, or its awards."""

from pathlib import Path

import pytest
from flask import Flask
from invenio_rdm_starter import community_views
from invenio_rdm_starter.community_views import (
    AwardsParam,
    CommunityRecordSearchOptions,
)
from invenio_records_resources.services.base.config import SearchConfig
from invenio_search.engine import dsl
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from marshmallow import ValidationError

ROOT = Path(__file__).parents[3]

WELLCOME = {
    "id": "c1",
    "slug": "wellcome",
    "metadata": {"title": "Wellcome Trust", "type": {"id": "funder"}},
}
WELLCOME_AWARDS = {**WELLCOME, "custom_fields": {"rs:records_view": "awards"}}
JOSS = {"id": "c2", "slug": "joss", "metadata": {"type": {"id": "journal"}}}

AWARD = {"term": {"metadata.resource_type.id": "award"}}


def _query(params: dict) -> dict:
    search = AwardsParam(config=None).apply(None, dsl.Search(), params)
    return search.to_dict().get("query", {})


@pytest.mark.parametrize(
    ("facets", "expected"),
    [
        ({"awards": ["only"]}, {"bool": {"filter": [AWARD]}}),
        (
            {"awards": ["exclude"]},
            {"bool": {"filter": [{"bool": {"must_not": [AWARD]}}]}},
        ),
        ({"awards": "only"}, {"bool": {"filter": [AWARD]}}),
        ({"awards": ["anything"]}, {}),
        ({}, {}),
    ],
)
def test_the_awards_parameter_narrows_the_query(facets, expected):
    assert _query({"facets": facets}) == expected


def test_without_facets_the_search_is_as_it_is():
    assert _query({}) == {}


def test_a_community_s_record_search_takes_the_parameter():
    """Also once InvenioRDM has given the options the configured facets."""
    options = CommunityRecordSearchOptions.customize(
        SearchConfig({"facets": []}, facets={})
    )

    assert AwardsParam in options.params_interpreters_cls
    assert len(options.params_interpreters_cls) == len(
        set(options.params_interpreters_cls)
    )


@pytest.mark.parametrize(
    ("community", "toggle"),
    [(WELLCOME, True), (JOSS, False), ({"metadata": {}}, False), ({}, False)],
)
def test_a_funder_community_has_the_switch(community, toggle):
    assert community_views.awards_toggle(community) is toggle


def test_a_funder_community_s_search_starts_with_its_works():
    config = {
        "appId": "x",
        "initialQueryState": {"filters": [["language", "eng"], ["awards", "only"]]},
    }

    started = community_views.community_search_config(config, WELLCOME)

    assert started["initialQueryState"]["filters"] == [
        ["language", "eng"],
        ["awards", "exclude"],
    ]
    # The config it was given is left as it was.
    assert config["initialQueryState"]["filters"][-1] == ["awards", "only"]


@pytest.mark.parametrize(
    ("custom_fields", "expected"),
    [
        ({"rs:records_view": "awards"}, "only"),
        ({"rs:records_view": "works"}, "exclude"),
        ({"rs:records_view": "anything"}, "exclude"),
        ({}, "exclude"),
        (None, "exclude"),
    ],
)
def test_a_funder_community_s_setting_says_what_its_search_starts_with(
    custom_fields, expected
):
    community = {**WELLCOME, "custom_fields": custom_fields}
    config = {"appId": "x", "initialQueryState": {"filters": []}}

    started = community_views.community_search_config(config, community)

    assert started["initialQueryState"]["filters"] == [["awards", expected]]
    assert community_views.awards_filter(community) == expected


def test_the_setting_takes_works_or_awards():
    from invenio_rdm_starter.custom_fields import STARTER_PACK_CUSTOM_FIELDS

    (field,) = [f for f in STARTER_PACK_CUSTOM_FIELDS if f.name == "rs:records_view"]
    assert field.field.deserialize("awards") == "awards"
    with pytest.raises(ValidationError):
        field.field.deserialize("grants")


def test_another_community_s_search_starts_as_invenio_s():
    config = {"appId": "x", "initialQueryState": {"filters": []}}

    assert community_views.community_search_config(config, JOSS) is config


def _render(community: dict) -> str:
    app = Flask(__name__)
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(ROOT / "templates/semantic-ui")),
            DictLoader(
                {
                    "invenio_communities/details/base.html": (
                        "{% block javascript %}{% endblock %}"
                        "{% block page_body %}{% endblock %}"
                    )
                }
            ),
        ]
    )
    app.jinja_env.globals.update(
        _=lambda s: s,
        webpack={"invenio-app-rdm-community-records-search.js": ""},
        starter_awards_toggle=community_views.awards_toggle,
        starter_awards_filter=community_views.awards_filter,
        starter_community_search_config=community_views.community_search_config,
        search_app_communities_records_config=lambda **kwargs: {
            "appId": kwargs["app_id"],
            "initialQueryState": {"filters": []},
        },
    )
    with app.test_request_context():
        return app.jinja_env.get_template(
            "invenio_communities/records/index.html"
        ).render(
            community={"metadata": {"title": "A community"}},
            community_ui=community,
            endpoint="/api/communities/c1/records",
        )


def test_a_funder_s_records_page_marks_the_switch_and_starts_with_works():
    html = _render(WELLCOME)

    assert (
        '<div hidden data-starter-awards-toggle data-title="Awards" '
        'data-label="View awards" data-default="exclude"></div>'
    ) in html
    assert "[&#34;awards&#34;, &#34;exclude&#34;]" in html or (
        '["awards", "exclude"]' in html
    )


def test_a_funder_s_records_page_opening_with_awards_says_so():
    html = _render(WELLCOME_AWARDS)

    assert 'data-default="only"' in html
    assert "[&#34;awards&#34;, &#34;only&#34;]" in html or (
        '["awards", "only"]' in html
    )


def test_another_records_page_is_invenio_s():
    html = _render(JOSS)

    assert "data-starter-awards-toggle" not in html
    assert "awards" not in html
    assert "InvenioCommunities.DetailsSearch" in html
