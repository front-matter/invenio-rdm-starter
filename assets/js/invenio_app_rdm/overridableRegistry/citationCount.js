// This file is part of InvenioRDM Starter
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

// A search result's citations, beside its views and downloads (CompactStats):
// how many works cite this version of the record, among those the commonmeta
// store knows. invenio-pidbox writes the count into the search document
// (custom field pidbox:citation_count); a result indexed before it has the
// citations themselves, which are counted instead.

import { i18next } from "@translations/invenio_app_rdm/i18next";
import _get from "lodash/get";
import React from "react";
import { Icon, Label, Popup } from "semantic-ui-react";
import { localizedFormatNumber } from "@js/invenio_app_rdm/utils";

export function citationCount(result) {
  const count = _get(result, ["custom_fields", "pidbox:citation_count"]);
  if (typeof count === "number") {
    return count;
  }
  const citations = _get(result, ["custom_fields", "pidbox:citations"]);
  return Array.isArray(citations) ? citations.length : null;
}

export const CitationCount = ({ result }) => {
  const count = citationCount(result);
  if (count == null) {
    return null;
  }
  return (
    <Popup
      size="tiny"
      content={i18next.t("Citations")}
      trigger={
        <Label className="transparent">
          <Icon name="quote left" />
          {localizedFormatNumber(count)}
        </Label>
      }
    />
  );
};
