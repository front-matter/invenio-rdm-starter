"""A page of a record's citations or references, for the record page's pagers.

The works citing a record are kept by invenio-pidbox in ``pidbox_relations``,
not in the record; its references are its own list, in its metadata
(``invenio_pidbox.graph``). The record page
(templates/semantic-ui/invenio_app_rdm/records/details/details.html) shows
each a page at a time (``STARTER_CITATIONS_PAGE_SIZE``): the citations newest
first, the references in their order. Each work invenio-pidbox's Read works
job has read is rendered from its CSL JSON, in the instance's citation style
and the reader's language; any other is shown by its DOI, or a reference by
the text deposited for it.

The first page, or the one its ``citations_page`` or ``references_page`` asks
for, comes with the record page. Its pager fetches the others from
``/records/<pid_value>/citations?page=N`` and ``.../references?page=N``: one
page as HTML, rendered by the same macro (``show_paged``), which replaces the
one shown.
"""

from __future__ import annotations

from typing import Any

import structlog
from flask import current_app, g, render_template, request
from flask_babel import get_locale
from invenio_pidbox import graph
from invenio_rdm_records.proxies import current_rdm_records_service

TEMPLATE = "invenio_rdm_starter/citations.html"
REFERENCES_TEMPLATE = "invenio_rdm_starter/references.html"

log = structlog.get_logger().bind(service="citations")


def page_number(value: Any) -> int:
    """The page a request asks for: 1 for none or one that isn't a number."""
    try:
        return max(int(value), 1)
    except TypeError, ValueError:
        return 1


def reader_locale() -> str | None:
    """The reader's language, which a citation is rendered in."""
    try:
        locale = get_locale()
    except Exception:  # noqa: BLE001 - outside a request: the default
        return None
    return str(locale).replace("_", "-") if locale else None


def _pages(total: int, page: Any, size: int) -> tuple[int, int]:
    """The pages there are, and the one asked for clamped to them."""
    pages = max((total + size - 1) // size, 1)
    return pages, min(page_number(page), pages)


def citation_count(doi: str | None) -> int:
    """How many works cite the record with ``doi``."""
    return graph.count_citations(doi) if doi else 0


def citations_page(
    doi: str | None, page: Any, size: int | None = None
) -> dict[str, Any]:
    """One page of a record's citations and what its pager needs.

    ``{"entries", "page", "pages", "total", "size", "first"}``: the entries
    of the page, numbered from ``first``, the page clamped to those there are.
    """
    size = size or current_app.config["STARTER_CITATIONS_PAGE_SIZE"]
    total = citation_count(doi)
    pages, page = _pages(total, page, size)
    entries: list[dict[str, Any]] = []
    if total:
        entries, _total = graph.read_citations(doi, page, size, locale=reader_locale())
        if not entries:
            log.warning("citations page empty", doi=doi, page=page, total=total)

    return {
        "entries": entries,
        "page": page,
        "pages": pages,
        "total": total,
        "size": size,
        "first": (page - 1) * size + 1,
    }


def references_page(
    references: list[dict[str, Any]] | None, page: Any, size: int | None = None
) -> dict[str, Any]:
    """One page of a record's references, in their order, as for citations."""
    size = size or current_app.config["STARTER_CITATIONS_PAGE_SIZE"]
    references = [entry for entry in references or [] if isinstance(entry, dict)]
    total = len(references)
    pages, page = _pages(total, page, size)
    first = (page - 1) * size
    entries = graph.read_references(
        references[first : first + size], locale=reader_locale()
    )
    return {
        "entries": entries,
        "page": page,
        "pages": pages,
        "total": total,
        "size": size,
        "first": first + 1,
    }


def default_community_slug(record: Any) -> str | None:
    """The slug of the record's default community, which its links search."""
    community = record.parent.communities.default
    return getattr(community, "slug", None) if community else None


def record_citations(pid_value: str) -> tuple[str, int]:
    """One page of the published record's citations, as HTML."""
    item = current_rdm_records_service.read(g.identity, pid_value)
    doi = ((item.data.get("pids") or {}).get("doi") or {}).get("identifier")
    return (
        render_template(
            TEMPLATE,
            citations=citations_page(doi, request.args.get("page")),
            record_id=item.id,
            community_slug=default_community_slug(item._record),
        ),
        200,
    )


def record_references(pid_value: str) -> tuple[str, int]:
    """One page of the published record's references, as HTML."""
    item = current_rdm_records_service.read(g.identity, pid_value)
    references = (item.data.get("metadata") or {}).get("references")
    return (
        render_template(
            REFERENCES_TEMPLATE,
            references=references_page(references, request.args.get("page")),
            record_id=item.id,
            community_slug=default_community_slug(item._record),
        ),
        200,
    )
