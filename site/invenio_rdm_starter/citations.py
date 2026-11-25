"""A page of a record's citations, for the record page's pager.

The works citing a record are kept by invenio-pidbox in ``pidbox_relations``,
not in the record (``invenio_pidbox.graph``). The record page
(templates/semantic-ui/invenio_app_rdm/records/details/details.html) shows them
a page at a time (``STARTER_CITATIONS_PAGE_SIZE``), newest first, each as its
formatted citation, or by its DOI until invenio-pidbox's Format citations job
has formatted it.

The first page, or the one its ``citations_page`` asks for, comes with the
record page. Its pager fetches the others from
``/records/<pid_value>/citations?page=N``: one page as HTML, rendered by the
same macro (``show_citations``), which replaces the one shown.
"""

from __future__ import annotations

from typing import Any

import structlog
from flask import current_app, g, render_template, request
from invenio_pidbox import graph
from invenio_rdm_records.proxies import current_rdm_records_service

TEMPLATE = "invenio_rdm_starter/citations.html"

log = structlog.get_logger().bind(service="citations")


def page_number(value: Any) -> int:
    """The page a request asks for: 1 for none or one that isn't a number."""
    try:
        return max(int(value), 1)
    except TypeError, ValueError:
        return 1


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
    pages = max((total + size - 1) // size, 1)
    page = min(page_number(page), pages)
    entries: list[dict[str, Any]] = []
    if total:
        entries, _total = graph.read_citations(doi, page, size)
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
