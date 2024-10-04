// This file is part of InvenioRDM
// Copyright (C) 2023 CERN.
//
// Invenio App RDM is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

/**
 * Add here all the overridden components of your app.
 */

import RecordsResultsListItem from "./RecordsResultsListItem";

export const overriddenComponents = {
  // frontpage
  "InvenioAppRDM.RecordsList.RecordsResultsListItem.layout": RecordsResultsListItem,
  // search page
  "InvenioAppRdm.Search.RecordsResultsListItem.layout": RecordsResultsListItem,
};
