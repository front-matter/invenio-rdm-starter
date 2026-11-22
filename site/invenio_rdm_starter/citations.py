"""A page of a record's citations, for the record page's pager.

A record's ``pidbox:citations`` can list thousands of works; the record page
(templates/semantic-ui/invenio_app_rdm/records/details/details.html) shows
them a page at a time (``STARTER_CITATIONS_PAGE_SIZE``), the first page, or the
one its ``citations_page`` asks for, with the page itself. Its pager fetches
the others from ``/records/<pid_value>/citations?page=N``: one page as HTML,
rendered by the same macro (``show_citations``), which replaces the one shown.
"""

from __future__ import annotations

from typing import Any

from flask import current_app, g, render_template, request
from invenio_pidbox.custom_fields import CITATIONS_FIELD
from invenio_rdm_records.proxies import current_rdm_records_service

TEMPLATE = "invenio_rdm_starter/citations.html"


def page_number(value: Any) -> int:
    """The page a request asks for: 1 for none or one that isn't a number."""
    try:
        return max(int(value), 1)
    except TypeError, ValueError:
        return 1


def default_community_slug(record: Any) -> str | None:
    """The slug of the record's default community, which its links search."""
    community = record.parent.communities.default
    return getattr(community, "slug", None) if community else None


def record_citations(pid_value: str) -> tuple[str, int]:
    """One page of the published record's citations, as HTML."""
    item = current_rdm_records_service.read(g.identity, pid_value)
    citations = (item.data.get("custom_fields") or {}).get(CITATIONS_FIELD) or []
    return (
        render_template(
            TEMPLATE,
            citations=citations,
            record_id=item.id,
            community_slug=default_community_slug(item._record),
            page=page_number(request.args.get("page")),
            size=current_app.config["STARTER_CITATIONS_PAGE_SIZE"],
        ),
        200,
    )
