"""A page of a record's citations, for the record page's pager.

A record's ``pidbox:citations`` holds its newest citations, at most
invenio-pidbox's ``PIDBOX_CITATIONS_MAX``, and ``pidbox:citation_count`` the
number of them all where that is more (a DOI cited twenty thousand times). The
record page (templates/semantic-ui/invenio_app_rdm/records/details/details.html)
shows them a page at a time (``STARTER_CITATIONS_PAGE_SIZE``): a page of the
stored ones from the record, a page past them from the commonmeta store, which
reads and formats only that page (``invenio_pidbox.tasks.citation_page``).

The first page, or the one its ``citations_page`` asks for, comes with the
record page. Its pager fetches the others from
``/records/<pid_value>/citations?page=N``: one page as HTML, rendered by the
same macro (``show_citations``), which replaces the one shown.
"""

from __future__ import annotations

from typing import Any

import structlog
from flask import current_app, g, render_template, request
from invenio_pidbox.custom_fields import CITATION_COUNT_FIELD, CITATIONS_FIELD
from invenio_pidbox.tasks import citation_page
from invenio_rdm_records.proxies import current_rdm_records_service

TEMPLATE = "invenio_rdm_starter/citations.html"

log = structlog.get_logger().bind(service="citations")


def page_number(value: Any) -> int:
    """The page a request asks for: 1 for none or one that isn't a number."""
    try:
        return max(int(value), 1)
    except TypeError, ValueError:
        return 1


def citation_count(custom_fields: dict[str, Any] | None) -> int:
    """How many works cite a record: the stored count where it's more."""
    fields = custom_fields or {}
    count = len(fields.get(CITATIONS_FIELD) or [])
    stored = fields.get(CITATION_COUNT_FIELD)
    if isinstance(stored, int) and not isinstance(stored, bool) and stored > count:
        return stored
    return count


def citations_page(
    custom_fields: dict[str, Any] | None,
    doi: str | None,
    page: Any,
    size: int | None = None,
) -> dict[str, Any]:
    """One page of a record's citations and what its pager needs.

    ``{"entries", "page", "pages", "total", "size", "first"}``: the entries
    of the page, numbered from ``first``, the page clamped to those there are.
    A page past the stored citations is read from the store; when the store
    doesn't answer it is empty, and the pager still offers the others.
    """
    size = size or current_app.config["STARTER_CITATIONS_PAGE_SIZE"]
    stored = (custom_fields or {}).get(CITATIONS_FIELD) or []
    total = citation_count(custom_fields)
    pages = max((total + size - 1) // size, 1)
    page = min(page_number(page), pages)
    first = (page - 1) * size

    entries = stored[first : first + size]
    if first + size > len(stored) and total > len(stored) and doi:
        read = citation_page(
            current_app.config.get("PIDBOX_SQLITE_PATH") or "",
            doi,
            page,
            size,
            stored,
        )
        if read is None:
            log.warning("citations page unavailable", doi=doi, page=page)
        else:
            entries = read[0]

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
            citations=citations_page(
                item.data.get("custom_fields"), doi, request.args.get("page")
            ),
            record_id=item.id,
            community_slug=default_community_slug(item._record),
        ),
        200,
    )
