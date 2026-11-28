// This file is part of InvenioRDM Starter
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

/**
 * A funder community's records, switched between the works it funded and its
 * awards (the grants it made), in the search sidebar as InvenioRDM switches
 * between the latest and all versions.
 *
 * The switch is a filter of its own, `awards`: `exclude` while it is off, the
 * works, and `only` while it is on, the awards. The Starter's search params
 * interpreter (invenio_rdm_starter.community_views.AwardsParam) applies it to
 * the query, so the facets count what the list shows. The page says the
 * community is a funder's by a marker the Starter's records template renders,
 * with the switch's title and label in the page's language, and the filter the
 * community's setting (rs:records_view) opens the page with; elsewhere there
 * is no switch, and no filter.
 */

import React, { useEffect } from "react";
import PropTypes from "prop-types";
import { Card, Checkbox } from "semantic-ui-react";
import { withState } from "react-searchkit";
import { ContribSearchAppFacets } from "@js/invenio_search_ui/components";

export const AWARDS = "awards";
export const ONLY = [AWARDS, "only"];
export const EXCLUDE = [AWARDS, "exclude"];

/** The marker of a funder community's records page, or null. */
export function awardsToggleMarker(doc = document) {
  return doc.querySelector("[data-starter-awards-toggle]");
}

/** The awards filter among the search's filters: "only", "exclude" or null. */
export function awardsFilter(filters) {
  const found = (filters || []).find((filter) => filter[0] === AWARDS);
  return found ? found[1] : null;
}

/** The filters to toggle to switch to the other view, from `current`. */
export function switchFilters(current) {
  if (current === "only") return [ONLY, EXCLUDE];
  if (current === "exclude") return [EXCLUDE, ONLY];
  return [ONLY];
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
      updateQueryState({ filters: [initial === "only" ? ONLY : EXCLUDE] });
    }
  }, [current, initial, updateQueryState]);

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
          onClick={() => updateQueryState({ filters: switchFilters(current) })}
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
 * A community records search's facets: InvenioRDM's, with its versions switch,
 * and the awards switch above them on a funder community's page.
 */
export const CommunityRecordsFacets = (props) => {
  const marker = awardsToggleMarker();
  return (
    <>
      {marker && (
        <AwardsToggle
          title={marker.dataset.title}
          label={marker.dataset.label}
          initial={marker.dataset.default}
        />
      )}
      <ContribSearchAppFacets {...props} toggle />
    </>
  );
};
