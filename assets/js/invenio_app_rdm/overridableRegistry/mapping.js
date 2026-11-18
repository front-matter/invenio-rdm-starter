// This file is part of InvenioRDM Starter
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

/**
 * The components the Starter overrides. This file replaces invenio-app-rdm's
 * empty mapping.js when the Docker build copies the assets directory over the
 * one `invenio webpack create` generates.
 */

import RecordsResultsListItem from "./RecordsResultsListItem";

export const overriddenComponents = {
  RecordsResultsListItem: RecordsResultsListItem,
};
