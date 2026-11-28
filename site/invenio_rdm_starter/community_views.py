"""A funder's community, switched between the works it funded and its awards.

A funder's Starter Pack (``wellcome``) holds the grants the funder made, records
of resource type Award, and the works they funded. Its records search has a
switch in the sidebar, as InvenioRDM has for versions: off, the works; on, the
awards. The switch is the search parameter ``awards`` (:class:`AwardsParam`):
``exclude`` leaves the awards out, ``only`` keeps them alone. It narrows the
query rather than filtering the hits after it, as the versions switch does, so
the facets count what the list shows.

The parameter is the community record search's, through the search options
class ``RDM_COMMUNITY_RECORD_SEARCH_OPTIONS_CLS`` names
(:class:`CommunityRecordSearchOptions`). The switch itself is the Starter's
(``assets/js/.../AwardsToggle.js``), shown where the records template marks the
page as a funder community's (``starter_awards_toggle``), which also starts the
search with the works or the awards, as the community's setting
``rs:records_view`` says (``starter_community_search_config``). Loaded through
the ``invenio_base.finalize_app`` entry point
``invenio_rdm_starter_community_views``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, ClassVar

from flask import Flask
from invenio_rdm_records.services.config import RDMCommunityRecordSearchOptions
from invenio_records_resources.services.records.params.base import ParamInterpreter

from invenio_rdm_starter.custom_fields import (
    DEFAULT_RECORDS_VIEW,
    RECORDS_VIEW_FIELD,
    RECORDS_VIEWS,
)

#: The community types whose records search has the awards switch.
TYPES_WITH_AWARDS_TOGGLE = ("funder",)

#: The search parameter of the switch, and its values.
AWARDS_PARAM = "awards"
ONLY = "only"
EXCLUDE = "exclude"

#: Where a record's resource type is, and the type of a funder's grants.
RESOURCE_TYPE_FIELD = "metadata.resource_type.id"
AWARD_TYPE = "award"


class AwardsParam(ParamInterpreter):
    """Evaluate the ``awards`` parameter: ``only`` the awards, or ``exclude`` them.

    Any other value, or none, leaves the search as it is. The search request
    collects the parameter, which isn't one of its own, with the facets; the
    facets parameter skips it, as no facet has its name.
    """

    def apply(self, identity: Any, search: Any, params: dict[str, Any]) -> Any:
        """Narrow the query to the awards or to the other records."""
        values = (params.get("facets") or {}).get(AWARDS_PARAM) or []
        if isinstance(values, str):
            values = [values]
        if ONLY in values:
            return search.filter("term", **{RESOURCE_TYPE_FIELD: AWARD_TYPE})
        if EXCLUDE in values:
            return search.exclude("term", **{RESOURCE_TYPE_FIELD: AWARD_TYPE})
        return search


class CommunityRecordSearchOptions(RDMCommunityRecordSearchOptions):
    """InvenioRDM's community record search, with the ``awards`` parameter."""

    params_interpreters_cls: ClassVar[list[type]] = [
        *RDMCommunityRecordSearchOptions.params_interpreters_cls,
        AwardsParam,
    ]


def awards_toggle(community: dict[str, Any]) -> bool:
    """Whether a community's records search has the awards switch.

    ``community`` is the community as its page has it (``community_ui``).
    """
    community_type = ((community.get("metadata") or {}).get("type") or {}).get("id")
    return community_type in TYPES_WITH_AWARDS_TOGGLE


def records_view(community: dict[str, Any]) -> str:
    """What a funder community's records page opens with: works or awards.

    The community's setting ``rs:records_view``; works when it has none.
    """
    view = (community.get("custom_fields") or {}).get(RECORDS_VIEW_FIELD)
    return view if view in RECORDS_VIEWS else DEFAULT_RECORDS_VIEW


def awards_filter(community: dict[str, Any]) -> str:
    """The awards filter a funder community's records search starts with."""
    return ONLY if records_view(community) == "awards" else EXCLUDE


def community_search_config(
    config: dict[str, Any], community: dict[str, Any]
) -> dict[str, Any]:
    """A community records search's config, on a funder's starting as it says.

    The switch sets the filter as the search loads, but the first request would
    still be for every record; starting with it saves that request.
    """
    if not awards_toggle(community):
        return config
    config = deepcopy(config)
    state = config.setdefault("initialQueryState", {})
    filters = [f for f in state.get("filters") or [] if f[0] != AWARDS_PARAM]
    state["filters"] = [*filters, [AWARDS_PARAM, awards_filter(community)]]
    return config


def finalize_app(app: Flask) -> None:
    """Make ``starter_awards_toggle``, ``starter_awards_filter`` and
    ``starter_community_search_config`` template globals."""
    app.add_template_global(awards_toggle, "starter_awards_toggle")
    app.add_template_global(awards_filter, "starter_awards_filter")
    app.add_template_global(community_search_config, "starter_community_search_config")
