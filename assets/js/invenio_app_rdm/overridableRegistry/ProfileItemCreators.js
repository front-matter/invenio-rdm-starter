// This file is part of InvenioRDM Starter
// Copyright (C) 2020-2024 CERN.
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

// invenio-app-rdm v14's SearchItemCreators (utils.js), with a creator's name
// linking to their person page instead of to a search by name.

import { i18next } from "@translations/invenio_app_rdm/i18next";
import _get from "lodash/get";
import React from "react";

export function ProfileItemCreators({ creators, className, othersLink }) {
  let spanClass = "creatibutor-wrap separated";
  className && (spanClass += ` ${className}`);

  function makeIcon(scheme, identifier, name) {
    let link = null;
    let linkTitle = null;
    let icon = null;
    let alt = "";

    switch (scheme) {
      case "orcid":
        link = `https://orcid.org/${identifier}`;
        linkTitle = i18next.t("ORCID profile");
        icon = "/static/images/orcid.svg";
        alt = i18next.t("ORCID logo");
        break;
      case "ror":
        link = `https://ror.org/${identifier}`;
        linkTitle = i18next.t("ROR profile");
        icon = "/static/images/ror-icon.svg";
        alt = i18next.t("ROR logo");
        break;
      case "gnd":
        link = `https://d-nb.info/gnd/${identifier}`;
        linkTitle = i18next.t("GND profile");
        icon = "/static/images/gnd-icon.svg";
        alt = i18next.t("GND logo");
        break;
      default:
        return null;
    }

    icon = (
      <a
        className="no-text-decoration mr-0"
        href={link}
        aria-label={`${name}: ${linkTitle}`}
        title={`${name}: ${linkTitle}`}
        key={scheme}
      >
        <img className="inline-id-icon ml-5" src={icon} alt={alt} />
      </a>
    );
    return icon;
  }

  function getIcons(creator) {
    let ids = _get(creator, "person_or_org.identifiers", []);
    let creatorName = _get(creator, "person_or_org.name", i18next.t("No name"));
    let icons = ids.map((c) => makeIcon(c.scheme, c.identifier, creatorName));
    return icons;
  }

  function getLink(creator) {
    let creatorName = _get(creator, "person_or_org.name", i18next.t("No name"));
    // A creator with an ORCID iD links to their person page; invenio-pidbox
    // redirects to a search for their records when it has no profile for them.
    const orcid = _get(creator, "person_or_org.identifiers", []).find(
      (id) => id.scheme === "orcid"
    )?.identifier;
    let link = (
      <a
        className="creatibutor-link"
        href={
          orcid
            ? `/people/${encodeURIComponent(orcid)}`
            : `/search?q=metadata.creators.person_or_org.name:"${creatorName}"`
        }
        title={`${creatorName}: ${orcid ? i18next.t("Profile") : i18next.t("Search")}`}
      >
        <span className="creatibutor-name">{creatorName}</span>
      </a>
    );
    return link;
  }

  const numDisplayed = 3;
  const result = creators.slice(0, numDisplayed).map((creator) => (
    <span className={spanClass} key={creator.person_or_org.name}>
      {getLink(creator)}
      {getIcons(creator)}
    </span>
  ));

  const numExtra = creators.length - numDisplayed;
  if (0 < numExtra) {
    let text;
    if (numExtra === 1) {
      text = i18next.t("and {{count}} other", { count: numExtra });
    } else {
      text = i18next.t("and {{count}} others", { count: numExtra });
    }
    result.push(
      <span className={spanClass} key={text}>
        <a className="creatibutor-link" href={othersLink}>
          <span className="creatibutor-name">
            {i18next.t(text, { count: numExtra })}
          </span>
        </a>
      </span>
    );
  }

  return result;
}
