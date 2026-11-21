"""Communities for the OpenAlex subfields.

As on Rogue Scholar, every OpenAlex subfield has a community of type
``subject``: slug the subfield number (``3309``), title the subfield name,
website the subfield's OpenAlex page. A record belongs to the community of
each subfield among its subjects.

Two jobs, so that the communities exist before any record names them:

* :func:`create_subject_communities` creates the community of every subfield
  in the subjects vocabulary's ``Subfields`` scheme that doesn't have one.
* :func:`add_records_to_subject_communities` adds each record to the
  communities of its subfields. commonmeta-rs adds the subfields to a record
  as subjects when it enriches the record with OpenAlex; nothing in
  InvenioRDM acts on them. A subfield without a community is left alone, so
  the first job decides which communities there are. It then features the
  largest ones, for the front page's carousel of featured communities, while
  none is featured (:func:`feature_subject_communities`).

A record already in all its communities costs a comparison, a subfield with a
community a lookup, so both jobs go over everything on each run.

A stopgap until invenio-vocabularies carries the OpenAlex vocabularies and
creates these communities itself.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

import structlog
from celery import shared_task
from flask import current_app
from invenio_access.permissions import system_identity
from invenio_pidstore.errors import PIDDoesNotExistError

SUBFIELD_PREFIX = "https://openalex.org/subfields/"

#: The subfields in the subjects vocabulary.
VOCABULARY_QUERY = "scheme:Subfields"

#: Records with a subject from the vocabulary's OpenAlex subfields scheme.
#: The index keeps a subject's scheme, which the vocabulary fills in.
RECORD_QUERY = "metadata.subjects.scheme:Subfields"

#: Who can see, join and submit to a subject community: anyone, as on Rogue
#: Scholar. Records are added by the second job, not submitted by depositors.
COMMUNITY_ACCESS = {
    "visibility": "public",
    "members_visibility": "public",
    "member_policy": "open",
    "record_submission_policy": "open",
    "review_policy": "open",
}

#: How many communities are featured, unless STARTER_FEATURED_COMMUNITIES says
#: otherwise.
DEFAULT_FEATURED_COMMUNITIES = 5

log = structlog.get_logger().bind(service="subject_communities")


def record_subfields(record: dict[str, Any]) -> dict[str, str]:
    """Return the OpenAlex subfields of a record, as slug → name.

    The slug is the subfield number, the last part of its OpenAlex URL. A
    subfield without a name, as an index hit carries it before the vocabulary
    resolved it, gets its number as the name.
    """
    subfields: dict[str, str] = {}
    for subject in (record.get("metadata") or {}).get("subjects") or []:
        slug = subfield_slug(subject.get("id") or "")
        if slug is not None:
            subfields[slug] = subject.get("subject") or slug
    return subfields


def community_data(slug: str, name: str) -> dict[str, Any]:
    """Return the data of the subject community for one subfield."""
    return {
        "slug": slug,
        "access": dict(COMMUNITY_ACCESS),
        "metadata": {
            "title": name,
            "type": {"id": "subject"},
            "website": f"{SUBFIELD_PREFIX}{slug}",
        },
    }


def subfield_slug(subject_id: str) -> str | None:
    """Return a subfield's community slug, its number, or ``None``."""
    if not subject_id.startswith(SUBFIELD_PREFIX):
        return None
    slug = subject_id.removeprefix(SUBFIELD_PREFIX).strip("/")
    return slug if slug.isdigit() else None


def _community_id(slug: str) -> str | None:
    """Return the id of a subfield's community, or ``None`` if there is none."""
    from invenio_communities.proxies import current_communities

    try:
        return current_communities.service.read(system_identity, slug).id
    except PIDDoesNotExistError:
        return None


@shared_task(ignore_result=True)
def create_subject_communities() -> dict[str, int]:
    """Create the community of every OpenAlex subfield that has none.

    Returns counts of what it did, which is what a manual run shows:
    ``{"subfields", "existing", "created", "failed"}``.
    """
    from invenio_communities.proxies import current_communities
    from invenio_records_resources.proxies import current_service_registry

    subjects = current_service_registry.get("subjects")
    communities = current_communities.service
    counts = {"subfields": 0, "existing": 0, "created": 0, "failed": 0}

    for hit in subjects.scan(system_identity, params={"q": VOCABULARY_QUERY}).hits:
        slug = subfield_slug(hit.get("id") or "")
        if slug is None:
            continue
        counts["subfields"] += 1
        if _community_id(slug) is not None:
            counts["existing"] += 1
            continue

        name = hit.get("subject") or slug
        try:
            communities.create(system_identity, community_data(slug, name))
        except Exception:
            # One subfield failing must not stop the others; it is tried
            # again on the next run.
            counts["failed"] += 1
            log.exception("community_not_created", slug=slug, title=name)
            continue
        counts["created"] += 1
        log.info("community_created", slug=slug, title=name)

    log.info("subject_communities_created", **counts)
    return counts


@shared_task(ignore_result=True)
def add_records_to_subject_communities(
    max_records: int | None = None,
) -> dict[str, int]:
    """Add every record with OpenAlex subfields to their communities.

    Only to communities that exist: a subfield without one is counted under
    ``"no_community"`` and left for :func:`create_subject_communities`.
    Returns ``{"scanned", "added", "no_community", "failed"}``.
    """
    from invenio_communities.proxies import current_communities
    from invenio_rdm_records.proxies import current_rdm_records

    records = current_rdm_records.records_service
    record_communities = current_rdm_records.record_communities_service
    counts = {"scanned": 0, "added": 0, "no_community": 0, "failed": 0}
    community_ids: dict[str, str | None] = {}
    members: Counter[str] = Counter()

    for hit in records.scan(system_identity, params={"q": RECORD_QUERY}).hits:
        if max_records is not None and counts["scanned"] >= max_records:
            break
        counts["scanned"] += 1

        try:
            for slug in record_subfields(hit):
                if slug not in community_ids:
                    community_ids[slug] = _community_id(slug)
        except Exception:
            counts["failed"] += 1
            log.exception("community_lookup_failed", record_id=hit["id"])
            continue

        wanted = [community_ids[slug] for slug in record_subfields(hit)]
        counts["no_community"] += sum(1 for cid in wanted if cid is None)
        members.update(cid for cid in wanted if cid is not None)
        current = set(
            ((hit.get("parent") or {}).get("communities") or {}).get("ids") or []
        )
        missing = [cid for cid in wanted if cid is not None and cid not in current]
        if not missing:
            continue

        try:
            processed, errors = record_communities.add(
                system_identity,
                hit["id"],
                {"communities": [{"id": cid} for cid in missing]},
            )
        except Exception:
            counts["failed"] += 1
            log.exception("record_not_added", record_id=hit["id"])
            continue

        counts["added"] += 1 if processed else 0
        if errors:
            counts["failed"] += 1
            log.warning("record_partly_added", record_id=hit["id"], errors=errors)

    counts["featured"] = feature_subject_communities(
        current_communities.service,
        members,
        int(
            current_app.config.get(
                "STARTER_FEATURED_COMMUNITIES", DEFAULT_FEATURED_COMMUNITIES
            )
            or 0
        ),
    )
    log.info("records_added_to_subject_communities", **counts)
    return counts


def feature_subject_communities(
    communities: Any, members: Counter[str], count: int
) -> int:
    """Feature the ``count`` communities with the most records, from now.

    For the front page's carousel of featured communities, which shows nothing
    while none is featured. Only then: communities an admin features, under
    Administration > Communities, are theirs to choose, and stay as they are.
    ``members`` counts each community's records. Returns how many it featured.
    """
    if count <= 0 or not members:
        return 0
    if communities.featured_search(system_identity, params={"size": 1}).total:
        return 0
    start = datetime.now(UTC).isoformat()
    featured = 0
    for community_id, records in members.most_common(count):
        try:
            communities.featured_create(
                system_identity, community_id, {"start_date": start}
            )
        except Exception:
            # One community failing leaves the others featured.
            log.exception("community_not_featured", community_id=community_id)
            continue
        featured += 1
        log.info("community_featured", community_id=community_id, records=records)
    return featured
