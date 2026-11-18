// This file is part of InvenioRDM Starter
// Copyright (C) 2026 Front Matter.
//
// InvenioRDM Starter is free software; you can redistribute it and/or modify it
// under the terms of the MIT License; see LICENSE file for more details.

import React from "react";

/**
 * Inline formatting a title may keep, as publishers deposit it in Crossref and
 * DataCite: italics for species and gene names, sub- and superscripts for
 * formulas. Any other element is replaced by its text.
 */
const KEPT_TAGS = new Set(["b", "strong", "i", "em", "u", "sub", "sup"]);

/** Elements whose content is not text a reader should see. */
const DROPPED_TAGS = new Set(["script", "style", "template", "noscript", "title"]);

const OMISSION = "...";

/**
 * A title stored as HTML, as React elements.
 *
 * The title is parsed into an inert document (DOMParser runs no scripts and
 * loads nothing) and rebuilt from its text and the kept tags, without their
 * attributes. Nothing is inserted as HTML, so a title can't run script.
 *
 * Like lodash's truncate, a title longer than `length` characters of text is
 * cut and ends in "...", the omission counting towards `length`. Tags stay
 * balanced because the text is cut, not the markup.
 */
export function titleElements(html, length = 100) {
  const doc = new DOMParser().parseFromString(html ?? "", "text/html");
  const text = doc.body.textContent ?? "";
  let remaining = text.length > length ? length - OMISSION.length : Infinity;

  const build = (node, key) => {
    if (remaining <= 0) return null;
    if (node.nodeType === Node.TEXT_NODE) {
      const value = node.textContent.slice(0, remaining);
      remaining -= value.length;
      return value;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return null;

    const tag = node.tagName.toLowerCase();
    if (DROPPED_TAGS.has(tag)) return null;
    const children = Array.from(node.childNodes)
      .map((child, index) => build(child, index))
      .filter((child) => child !== null && child !== "");
    return KEPT_TAGS.has(tag)
      ? React.createElement(tag, { key }, ...children)
      : React.createElement(React.Fragment, { key }, ...children);
  };

  const elements = Array.from(doc.body.childNodes)
    .map((child, index) => build(child, index))
    .filter((child) => child !== null && child !== "");
  if (text.length > length) elements.push(OMISSION);
  return elements;
}
