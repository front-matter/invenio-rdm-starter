// This file is part of InvenioRDM Starter
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

/**
 * A funder's or organization's community's records, switched between the
 * works and the awards (grants), in the search sidebar as InvenioRDM switches
 * between the latest and all versions.
 *
 * The switch is a filter of its own, `awards`: `exclude` while it is off, the
 * works, and `only` while it is on, the awards. The Starter's search params
 * interpreter (invenio_rdm_starter.community_views.AwardsParam) applies it to
 * the query, so the facets count what the list shows. The page says the
 * community has the switch by a marker the Starter's records template renders,
 * with the switch's title and label in the page's language, and the filter the
 * community's type opens the page with: the awards on a funder's, the works on
 * an organization's; elsewhere there is no switch, and no filter.
 */

import React, { useEffect } from "react";
import PropTypes from "prop-types";
import { Card, Checkbox } from "semantic-ui-react";
import { withState } from "react-searchkit";
import { ContribSearchAppFacets } from "@js/invenio_search_ui/components";

export const AWARDS = "awards";
export const ONLY = [AWARDS, "only"];
export const EXCLUDE = [AWARDS, "exclude"];

/** The marker of a records page with the awards switch, or null. */
export function awardsToggleMarker(doc = document) {
  return doc.querySelector("[data-awards-toggle]");
}

/** The awards filter among the search's filters: "only", "exclude" or null. */
export function awardsFilter(filters) {
  const found = (filters || []).find((filter) => filter[0] === AWARDS);
  return found ? found[1] : null;
}

/**
 * The search's state with `filter` as its awards filter, and the rest as it is.
 *
 * react-searchkit's updateQueryState doesn't merge a state into the current
 * one: it starts from its initial state (no query, no filters) and toggles the
 * filters it is given into it. So it is given the whole state, with the
 * filters as they should be.
 */
export function withAwardsFilter(queryState, filter) {
  const others = (queryState.filters || []).filter((f) => f[0] !== AWARDS);
  return { ...queryState, filters: [...others, filter], page: 1 };
}

const AwardsToggleComponent = ({
  currentQueryState,
  updateQueryState,
  title,
  label,
  initial,
}) => {
  const current = awardsFilter(currentQueryState.filters);

  // Without a filter, as after clearing them, what the community opens with.
  useEffect(() => {
    if (current === null) {
      updateQueryState(
        withAwardsFilter(currentQueryState, initial === "only" ? ONLY : EXCLUDE)
      );
    }
  }, [current, currentQueryState, initial, updateQueryState]);

  const checked = current === "only";
  return (
    <Card className="borderless facet">
      <Card.Content>
        <Card.Header as="h2">{title}</Card.Header>
      </Card.Content>
      <Card.Content>
        <Checkbox
          toggle
          label={<label aria-hidden="true">{label}</label>}
          name="awards-toggle"
          aria-label={label}
          onClick={() =>
            updateQueryState(
              withAwardsFilter(currentQueryState, checked ? EXCLUDE : ONLY)
            )
          }
          checked={checked}
        />
      </Card.Content>
    </Card>
  );
};

AwardsToggleComponent.propTypes = {
  currentQueryState: PropTypes.object.isRequired,
  updateQueryState: PropTypes.func.isRequired,
  title: PropTypes.string.isRequired,
  label: PropTypes.string.isRequired,
  initial: PropTypes.oneOf(["only", "exclude"]),
};

AwardsToggleComponent.defaultProps = {
  initial: "exclude",
};

export const AwardsToggle = withState(AwardsToggleComponent);

/**
 * The facets' config with the awards switch's `filter`: while it is on, a
 * facet with an `awardsTitle` (RDM_FACETS' "ui") takes it, as the author
 * facets count the awards' contributors then (AwardsTermsFacet).
 */
export function awardsAggs(aggs, filter) {
  if (filter !== "only") {
    return aggs;
  }
  return (aggs || []).map((agg) =>
    agg.awardsTitle ? { ...agg, title: agg.awardsTitle } : agg
  );
}

/**
 * A records search's facets: InvenioRDM's, with its versions switch, and the
 * awards switch above them where the page is marked for it: a funder's or
 * organization's community, and an organization's page with awards
 * (invenio-pidbox's PIDBOX_AWARDS_SWITCH).
 */
const RecordsFacetsComponent = ({
  currentQueryState,
  currentResultsState,
  updateQueryState,
  aggs,
  ...props
}) => {
  const marker = awardsToggleMarker();
  const filter = awardsFilter(currentQueryState?.filters);
  return (
    <>
      {marker && (
        <AwardsToggle
          title={marker.dataset.title}
          label={marker.dataset.label}
          initial={marker.dataset.default}
        />
      )}
      <ContribSearchAppFacets
        {...props}
        aggs={awardsAggs(aggs, filter)}
        toggle
      />
    </>
  );
};

RecordsFacetsComponent.propTypes = {
  currentQueryState: PropTypes.object,
  currentResultsState: PropTypes.object,
  updateQueryState: PropTypes.func,
  aggs: PropTypes.array.isRequired,
};

RecordsFacetsComponent.defaultProps = {
  currentQueryState: {},
  currentResultsState: {},
  updateQueryState: () => {},
};

export const RecordsFacets = withState(RecordsFacetsComponent);
