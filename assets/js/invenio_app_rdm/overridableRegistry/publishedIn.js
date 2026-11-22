// This file is part of InvenioRDM Starter
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

// "Published in: …" of a search result, its journal's title linked to the
// journal's container page (invenio-pidbox, /containers/<issn>), as the record
// page's sidebar links it. InvenioRDM writes the publishing information as one
// sentence, title first ("Journal of Open Source Software, 5(52), 2363, ISSN:
// 2475-9066, 2020."); the title found in it becomes the link, the rest stays
// text. Without the journal's title and ISSN (custom field journal:journal),
// or a title the sentence doesn't hold, the sentence stays as it was.

import { i18next } from "@translations/invenio_app_rdm/i18next";
import _get from "lodash/get";
import React from "react";

// Stands in for the publishing information while the sentence is translated,
// so that the translation keeps its own wording around it.
const MARKER = "\u0000";

export function containerLink(result) {
  const journal = _get(result, ["custom_fields", "journal:journal"], {}) || {};
  const title = journal.title;
  const issn = journal.issn;
  if (!title || !issn) {
    return null;
  }
  return { title, href: `/containers/${encodeURIComponent(issn)}` };
}

export const PublishedIn = ({ result, publishingInformation }) => {
  const sentence = i18next.t("Published in: {{- publishInfo }}", {
    publishInfo: MARKER,
  });
  const [before, after = ""] = sentence.split(MARKER);
  const link = containerLink(result);
  const at = link ? publishingInformation.indexOf(link.title) : -1;
  if (at < 0) {
    return (
      <>
        {before}
        {publishingInformation}
        {after}
      </>
    );
  }
  return (
    <>
      {before}
      {publishingInformation.slice(0, at)}
      <a href={link.href}>{link.title}</a>
      {publishingInformation.slice(at + link.title.length)}
      {after}
    </>
  );
};
