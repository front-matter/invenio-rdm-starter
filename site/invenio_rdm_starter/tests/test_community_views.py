"""Tests for a funder community's records search: its works, or its awards."""

from pathlib import Path

import pytest
from flask import Flask
from invenio_rdm_starter import community_views
from invenio_rdm_starter.community_views import (
    AwardsFacetsParam,
    AwardsParam,
    AwardsTermsFacet,
    CommunityRecordSearchOptions,
    RecordSearchOptions,
)
from invenio_records_resources.services.base.config import SearchConfig
from invenio_records_resources.services.records.params import FacetsParam
from invenio_search.engine import dsl
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader

ROOT = Path(__file__).parents[3]

WELLCOME = {
    "id": "c1",
    "slug": "wellcome",
    "metadata": {"title": "Wellcome Trust", "type": {"id": "funder"}},
}
MHH = {"id": "c3", "slug": "mhh", "metadata": {"type": {"id": "organization"}}}
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
    "options_cls", [CommunityRecordSearchOptions, RecordSearchOptions]
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("only", {"bool": {"filter": [AWARD]}}),
        ("exclude", {"bool": {"filter": [{"bool": {"must_not": [AWARD]}}]}}),
    ],
)
def test_the_parameter_survives_the_facets_parameter(options_cls, value, expected):
    """The interpreters run in their order; the facets one takes the facets.

    A community's records search, and the records search an organization's
    page lists its works with.
    """
    options = options_cls.customize(SearchConfig({"facets": []}, facets={}))
    params = {"facets": {"awards": [value]}}
    search = dsl.Search()
    for interpreter_cls in options.params_interpreters_cls:
        if interpreter_cls in (AwardsParam, AwardsFacetsParam):
            search = interpreter_cls(options).apply(None, search, params)

    assert search.to_dict().get("query") == expected
    assert options.params_interpreters_cls.index(
        AwardsParam
    ) < options.params_interpreters_cls.index(AwardsFacetsParam)


@pytest.mark.parametrize(
    ("community", "toggle"),
    [
        (WELLCOME, True),
        (MHH, True),
        (JOSS, False),
        ({"metadata": {}}, False),
        ({}, False),
    ],
)
def test_a_funder_community_has_the_switch(community, toggle):
    assert community_views.awards_toggle(community) is toggle


def test_a_funder_community_s_search_starts_with_its_awards():
    config = {
        "appId": "x",
        "initialQueryState": {"filters": [["language", "eng"], ["awards", "only"]]},
    }

    started = community_views.community_search_config(config, WELLCOME)

    assert started["initialQueryState"]["filters"] == [
        ["language", "eng"],
        ["awards", "only"],
    ]
    # The config it was given is left as it was.
    assert config["initialQueryState"]["filters"] == [
        ["language", "eng"],
        ["awards", "only"],
    ]
    assert started is not config


@pytest.mark.parametrize(
    ("community", "expected"),
    [(WELLCOME, "only"), (MHH, "exclude"), (JOSS, "exclude"), ({}, "exclude")],
)
def test_a_funder_s_records_open_with_awards_the_others_with_works(community, expected):
    assert community_views.awards_filter(community) == expected


def test_an_organization_community_s_search_starts_with_its_works():
    config = {"appId": "x", "initialQueryState": {"filters": [["awards", "only"]]}}

    started = community_views.community_search_config(config, MHH)

    assert started["initialQueryState"]["filters"] == [["awards", "exclude"]]


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


@pytest.mark.parametrize(
    ("community", "expected"), [(WELLCOME, "only"), (MHH, "exclude")]
)
def test_a_records_page_with_the_switch_marks_it_and_starts_as_its_type_says(
    community, expected
):
    html = _render(community)

    assert (
        '<div hidden data-awards-toggle data-title="Awards" '
        f'data-label="View awards" data-default="{expected}"></div>'
    ) in html
    assert f"[&#34;awards&#34;, &#34;{expected}&#34;]" in html or (
        f'["awards", "{expected}"]' in html
    )


def test_another_records_page_is_invenio_s():
    html = _render(JOSS)

    assert "data-awards-toggle" not in html
    assert "awards" not in html
    assert "InvenioCommunities.DetailsSearch" in html


FACETS = {
    "affiliations": AwardsTermsFacet(
        field="metadata.creators.affiliations.id",
        awards_field="metadata.contributors.affiliations.id",
        label="Author affiliations",
    ),
    "language": dsl.TermsFacet(field="metadata.languages.id"),
}


def _facets_search(awards: list[str] | None, selected: list[str] | None = None):
    options = RecordSearchOptions.customize(
        SearchConfig(
            {"facets": list(FACETS)},
            facets={name: {"facet": facet} for name, facet in FACETS.items()},
        )
    )
    facets = {"awards": awards} if awards else {}
    if selected:
        facets["affiliations"] = selected
    return (
        AwardsFacetsParam(options)
        .apply(None, dsl.Search(), {"facets": facets})
        .to_dict()
    )


@pytest.mark.parametrize(
    ("awards", "field"),
    [
        (["only"], "metadata.contributors.affiliations.id"),
        (["exclude"], "metadata.creators.affiliations.id"),
        (None, "metadata.creators.affiliations.id"),
    ],
)
def test_the_awards_count_their_contributors_affiliations(awards, field):
    search = _facets_search(awards, ["02jx3x895"])

    assert search["aggs"]["affiliations"]["terms"]["field"] == field
    assert search["post_filter"] == {"terms": {field: ["02jx3x895"]}}
    # A facet without a field for the awards is as it is.
    assert search["aggs"]["language"]["terms"]["field"] == "metadata.languages.id"


def test_a_facet_for_the_awards_leaves_the_configured_one_as_it_is():
    facet = FACETS["affiliations"]

    awards = facet.for_awards()

    assert awards._params["field"] == "metadata.contributors.affiliations.id"
    assert facet._params["field"] == "metadata.creators.affiliations.id"


@pytest.mark.parametrize(
    "options_cls", [CommunityRecordSearchOptions, RecordSearchOptions]
)
def test_the_searches_with_the_switch_take_the_facets_for_awards(options_cls):
    interpreters = options_cls.params_interpreters_cls

    assert AwardsFacetsParam in interpreters
    assert FacetsParam not in interpreters
    assert interpreters.index(AwardsParam) < interpreters.index(AwardsFacetsParam)


def test_the_configured_author_facets_count_the_awards_contributors():
    from invenio_rdm_starter import config

    for name, field in (
        ("affiliations", "metadata.contributors.affiliations.id"),
        (
            "author_identifiers",
            "metadata.contributors.person_or_org.identifiers.scheme",
        ),
    ):
        facet = config.RDM_FACETS[name]["facet"]
        assert isinstance(facet, AwardsTermsFacet)
        assert facet.awards_field == field
