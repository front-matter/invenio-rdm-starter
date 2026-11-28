"""A funder's or organization's community, switched between works and awards.

A funder's Starter Pack (``wellcome``) holds the grants the funder made, records
of resource type Award, and the works they funded; an organization's may hold
awards too. Their records search has a switch in the sidebar, as InvenioRDM has for versions: off, the works; on, the
awards. The switch is the search parameter ``awards`` (:class:`AwardsParam`):
``exclude`` leaves the awards out, ``only`` keeps them alone. It narrows the
query rather than filtering the hits after it, as the versions switch does, so
the facets count what the list shows.

The awards name their funder as creator and their investigators, with their
affiliations, as contributors. With the awards on, the facets for author
affiliations and author identifiers (:class:`AwardsTermsFacet`) count the
contributors instead, through the facets parameter (:class:`AwardsFacetsParam`).

The parameter is the community record search's, through the search options
class ``RDM_COMMUNITY_RECORD_SEARCH_OPTIONS_CLS`` names
(:class:`CommunityRecordSearchOptions`). The switch itself is the Starter's
(``assets/js/.../AwardsToggle.js``), shown where the records template marks the
page as a funder's or organization's community's (``starter_awards_toggle``), which also starts the
search with the awards on a funder's community and with the works on an
organization's (``starter_community_search_config``). Loaded through
the ``invenio_base.finalize_app`` entry point
``invenio_rdm_starter_community_views``.
"""

from __future__ import annotations

from copy import copy, deepcopy
from typing import Any, ClassVar

from flask import Flask
from invenio_rdm_records.services.config import (
    RDMCommunityRecordSearchOptions,
    RDMSearchOptions,
)
from invenio_records_resources.services.records.facets import TermsFacet
from invenio_records_resources.services.records.params import FacetsParam
from invenio_records_resources.services.records.params.base import ParamInterpreter

#: The community types whose records search has the awards switch.
TYPES_WITH_AWARDS_TOGGLE = ("funder", "organization")

#: The community types whose records page opens with the awards; the others
#: open with the works.
TYPES_OPENING_WITH_AWARDS = ("funder",)

#: The search parameter of the switch, and its values.
AWARDS_PARAM = "awards"
ONLY = "only"
EXCLUDE = "exclude"

#: Where a record's resource type is, and the type of a funder's grants.
RESOURCE_TYPE_FIELD = "metadata.resource_type.id"
AWARD_TYPE = "award"


def _awards_values(params: dict[str, Any]) -> list[str]:
    """The values of the ``awards`` parameter among the facets in ``params``."""
    values = (params.get("facets") or {}).get(AWARDS_PARAM) or []
    return [values] if isinstance(values, str) else list(values)


class AwardsParam(ParamInterpreter):
    """Evaluate the ``awards`` parameter: ``only`` the awards, or ``exclude`` them.

    Any other value, or none, leaves the search as it is. The search request
    collects the parameter, which isn't one of its own, with the facets; the
    facets parameter skips it, as no facet has its name.
    """

    def apply(self, identity: Any, search: Any, params: dict[str, Any]) -> Any:
        """Narrow the query to the awards or to the other records."""
        values = _awards_values(params)
        if ONLY in values:
            return search.filter("term", **{RESOURCE_TYPE_FIELD: AWARD_TYPE})
        if EXCLUDE in values:
            return search.exclude("term", **{RESOURCE_TYPE_FIELD: AWARD_TYPE})
        return search


class AwardsTermsFacet(TermsFacet):
    """A terms facet that counts another field in the awards alone.

    ``awards_field`` is the field it counts and filters on while the search
    has ``awards=only``, e.g. the contributors' affiliations where ``field``
    is the creators'.
    """

    def __init__(self, awards_field: str, **kwargs: Any) -> None:
        """Take the field for the awards, and the facet's own arguments."""
        self.awards_field = awards_field
        super().__init__(**kwargs)

    def for_awards(self) -> AwardsTermsFacet:
        """The same facet, on the field for the awards."""
        facet = copy(self)
        facet._params = {**self._params, "field": self.awards_field}
        return facet


class AwardsFacetsParam(FacetsParam):
    """InvenioRDM's facets parameter, with the awards' fields for the awards.

    With ``awards=only`` its :class:`AwardsTermsFacet` facets count and filter
    on their ``awards_field``; otherwise all facets are as configured.
    """

    awards_only = False

    @property
    def facets(self) -> dict[str, Any]:
        """The facets, those for the awards on their fields while they are on."""
        facets = super().facets
        if not self.awards_only:
            return facets
        return {
            name: facet.for_awards() if isinstance(facet, AwardsTermsFacet) else facet
            for name, facet in facets.items()
        }

    def apply(self, identity: Any, search: Any, params: dict[str, Any]) -> Any:
        """Evaluate the facets, on the awards' fields with ``awards=only``."""
        self.awards_only = ONLY in _awards_values(params)
        return super().apply(identity, search, params)


def _with_awards(interpreters: list[type]) -> list[type]:
    """The interpreters, the awards parameter first and the facets for awards."""
    return [
        AwardsParam,
        *(AwardsFacetsParam if cls is FacetsParam else cls for cls in interpreters),
    ]


class RecordSearchOptions(RDMSearchOptions):
    """InvenioRDM's records search, with the ``awards`` parameter.

    For an organization's page, whose list of works (invenio-pidbox's) is the
    records search: its awards switch (PIDBOX_AWARDS_SWITCH). As the
    community's, read before the facets parameter takes the facets.
    """

    params_interpreters_cls: ClassVar[list[type]] = _with_awards(
        RDMSearchOptions.params_interpreters_cls
    )


class CommunityRecordSearchOptions(RDMCommunityRecordSearchOptions):
    """InvenioRDM's community record search, with the ``awards`` parameter.

    The parameter is read first: the facets parameter takes the facets out of
    the params, and puts back only those it has.
    """

    params_interpreters_cls: ClassVar[list[type]] = _with_awards(
        RDMCommunityRecordSearchOptions.params_interpreters_cls
    )


def awards_toggle(community: dict[str, Any]) -> bool:
    """Whether a community's records search has the awards switch.

    ``community`` is the community as its page has it (``community_ui``).
    """
    return community_type(community) in TYPES_WITH_AWARDS_TOGGLE


def community_type(community: dict[str, Any]) -> str | None:
    """A community's type (``funder``, ``organization``, ...), or None."""
    return ((community.get("metadata") or {}).get("type") or {}).get("id")


def awards_filter(community: dict[str, Any]) -> str:
    """The awards filter a community's records search starts with.

    ``only``, the awards, on a funder's community; ``exclude``, the works, on
    any other.
    """
    return ONLY if community_type(community) in TYPES_OPENING_WITH_AWARDS else EXCLUDE


def community_search_config(
    config: dict[str, Any], community: dict[str, Any]
) -> dict[str, Any]:
    """A community records search's config, starting with its awards or works.

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
