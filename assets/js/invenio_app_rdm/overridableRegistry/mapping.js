// This file is part of InvenioRDM Starter
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

/**
 * The components the Starter overrides. This file replaces invenio-app-rdm's
 * empty mapping.js when the Docker build copies the assets directory over the
 * one `invenio webpack create` generates.
 *
 * The record list item replaces InvenioRDM's wherever it is looked up by its
 * own name. A community's and a collection's record searches don't look it up
 * by name: each passes InvenioRDM's item as its result component, so they are
 * given the Starter's directly, with their app names, under their result keys.
 */

import { parametrize } from "react-overridable";
import RecordsResultsListItem from "./RecordsResultsListItem";

const COMMUNITY_RECORDS = "InvenioCommunities.DetailsSearch";
const COLLECTION_RECORDS = "InvenioAppRDM.CollectionsSearch";

export const overriddenComponents = {
  RecordsResultsListItem: RecordsResultsListItem,
  [`${COMMUNITY_RECORDS}.ResultsList.item`]: parametrize(
    RecordsResultsListItem,
    {
      appName: COMMUNITY_RECORDS,
    }
  ),
  [`${COLLECTION_RECORDS}.ResultsList.item`]: parametrize(
    RecordsResultsListItem,
    {
      appName: COLLECTION_RECORDS,
    }
  ),
};
