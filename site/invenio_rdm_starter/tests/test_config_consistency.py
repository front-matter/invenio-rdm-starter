"""Tests that the Starter's settings fit InvenioRDM's own.

The Starter replaces settings that InvenioRDM's search configurations look
into: a search names its sort options and facets, and RDM_SORT_OPTIONS and
RDM_FACETS have to hold them. A name missing there fails only when a page
builds that search. A pre-v14 RDM_SORT_OPTIONS without newestactivity made
every record landing page fail with KeyError, shown as "Page not found".
"""

from functools import cache

import pytest
from invenio_app_rdm import config as app_rdm_config
from invenio_rdm_records import config as rdm_config
from invenio_rdm_starter import config as starter_config


@cache
def _config() -> dict:
    """The settings as the app sees them, for the modules involved.

    invenio-rdm-records' defaults first (its extension only fills in what is
    missing), then the config modules in the order invenio-config loads them:
    invenio-app-rdm, then the Starter.
    """
    merged: dict = {}
    for module in (rdm_config, app_rdm_config, starter_config):
        merged.update({k: getattr(module, k) for k in dir(module) if k.isupper()})
    return merged


#: Searches built against RDM_SORT_OPTIONS (invenio-rdm-records' service
#: configs and invenio-app-rdm's search apps, the landing page sidebar's
#: request search among them).
SORTED_BY_RDM_SORT_OPTIONS = [
    "RDM_SEARCH",
    "RDM_SEARCH_DRAFTS",
    "RDM_SEARCH_VERSIONING",
    "RDM_SEARCH_USER_REQUESTS",
    "RDM_SEARCH_USER_COMMUNITIES",
    "COMMUNITIES_RECORDS_SEARCH",
]

#: Searches whose facets come from RDM_FACETS. The user requests and
#: communities searches take theirs from REQUESTS_FACETS and
#: COMMUNITIES_FACETS.
FACETED_BY_RDM_FACETS = [
    "RDM_SEARCH",
    "RDM_SEARCH_DRAFTS",
    "RDM_SEARCH_VERSIONING",
    "COMMUNITIES_RECORDS_SEARCH",
]


@pytest.mark.parametrize("search", SORTED_BY_RDM_SORT_OPTIONS)
def test_every_sort_option_a_search_names_exists(search):
    config = _config()
    wanted = set(config[search].get("sort", []))
    wanted |= {
        config[search][key]
        for key in ("sort_default", "sort_default_no_query")
        if key in config[search]
    }

    assert wanted <= set(config["RDM_SORT_OPTIONS"]), sorted(
        wanted - set(config["RDM_SORT_OPTIONS"])
    )


@pytest.mark.parametrize("search", FACETED_BY_RDM_FACETS)
def test_every_facet_a_search_names_exists(search):
    config = _config()
    wanted = set(config[search].get("facets", []))

    assert wanted <= set(config["RDM_FACETS"]), sorted(
        wanted - set(config["RDM_FACETS"])
    )


@pytest.mark.parametrize(
    "setting",
    ["RDM_SORT_OPTIONS", "RDM_FACETS", "RDM_RECORDS_IDENTIFIERS_SCHEMES"],
)
def test_the_starter_keeps_every_entry_invenio_rdm_defines(setting):
    """Extended, not copied: what a release adds arrives with it."""
    missing = set(getattr(rdm_config, setting)) - set(getattr(starter_config, setting))

    assert not missing, sorted(missing)


def test_other_is_the_last_identifier_scheme():
    assert list(starter_config.RDM_RECORDS_IDENTIFIERS_SCHEMES)[-1] == "other"


def test_no_helper_reaches_the_app_config():
    """Flask copies every name for which name.isupper() is true.

    That includes names with a leading underscore ("_HELPER".isupper() is
    True), so helpers of the config module are written in lower case.
    """
    leaked = [k for k in dir(starter_config) if k.isupper() and k.startswith("_")]

    assert not leaked, leaked
