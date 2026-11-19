"""Communities for the OpenAlex subfields of the records.

As on Rogue Scholar, every OpenAlex subfield the records name has a community
of type ``subject``: slug the subfield number (``3309``), title the subfield
name, website the subfield's OpenAlex page. A record belongs to the community
of each subfield among its subjects.

commonmeta-rs adds the subfields to a record as subjects from the
``Subfields`` scheme of the subjects vocabulary, when it enriches the record
with OpenAlex. Nothing in InvenioRDM acts on them, so a sweep does: it
creates a community the first time a subfield turns up, and adds a record to
the communities of its subfields that it is not in yet. A record in all of
them costs a comparison and nothing else, so the sweep runs over every record
with a subfield on each run.

A stopgap until invenio-vocabularies carries the OpenAlex vocabularies and
creates these communities itself.
"""

from __future__ import annotations

from typing import Any

import structlog
from celery import shared_task
from invenio_access.permissions import system_identity
from invenio_pidstore.errors import PIDDoesNotExistError

SUBFIELD_PREFIX = "https://openalex.org/subfields/"

#: Records with a subject from the vocabulary's OpenAlex subfields scheme.
#: The index keeps a subject's scheme, which the vocabulary fills in.
SUBFIELD_QUERY = "metadata.subjects.scheme:Subfields"

#: Who can see, join and submit to a subject community: anyone, as on Rogue
#: Scholar. Records are added by this sweep, not submitted by depositors.
COMMUNITY_ACCESS = {
    "visibility": "public",
    "members_visibility": "public",
    "member_policy": "open",
    "record_submission_policy": "open",
    "review_policy": "open",
}

log = structlog.get_logger().bind(service="subject_communities")


def record_subfields(record: dict[str, Any]) -> dict[str, str]:
    """Return the OpenAlex subfields of a record, as slug → name.

    The slug is the subfield number, the last part of its OpenAlex URL. A
    subfield without a name, as an index hit carries it before the vocabulary
    resolved it, gets its number as the name.
    """
    subfields: dict[str, str] = {}
    for subject in (record.get("metadata") or {}).get("subjects") or []:
        subject_id = subject.get("id") or ""
        if not subject_id.startswith(SUBFIELD_PREFIX):
            continue
        slug = subject_id.removeprefix(SUBFIELD_PREFIX).strip("/")
        if slug.isdigit():
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


def _community_id(slug: str, name: str, counts: dict[str, int]) -> str:
    """Return the id of a subfield's community, creating it if needed."""
    from invenio_communities.proxies import current_communities

    service = current_communities.service
    try:
        return service.read(system_identity, slug).id
    except PIDDoesNotExistError:
        community = service.create(system_identity, community_data(slug, name))
        counts["communities_created"] += 1
        log.info("community_created", slug=slug, title=name)
        return community.id


@shared_task(ignore_result=True)
def sync_subject_communities(max_records: int | None = None) -> dict[str, int]:
    """Put every record with OpenAlex subfields into their communities.

    Returns counts of what it did, which is what a manual run shows:
    ``{"scanned", "communities_created", "records_added", "failed"}``.
    """
    from invenio_rdm_records.proxies import current_rdm_records

    records = current_rdm_records.records_service
    record_communities = current_rdm_records.record_communities_service
    counts = {"scanned": 0, "communities_created": 0, "records_added": 0, "failed": 0}
    community_ids: dict[str, str] = {}

    for hit in records.scan(system_identity, params={"q": SUBFIELD_QUERY}).hits:
        if max_records is not None and counts["scanned"] >= max_records:
            break
        counts["scanned"] += 1

        subfields = record_subfields(hit)
        try:
            for slug, name in subfields.items():
                if slug not in community_ids:
                    community_ids[slug] = _community_id(slug, name, counts)
        except Exception:
            # The community of one subfield failing to be created must not
            # stop the sweep; the record is tried again on the next run.
            counts["failed"] += 1
            log.exception("community_creation_failed", record_id=hit["id"])
            continue

        current = set(
            ((hit.get("parent") or {}).get("communities") or {}).get("ids") or []
        )
        missing = [
            community_ids[s] for s in subfields if community_ids[s] not in current
        ]
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

        counts["records_added"] += 1 if processed else 0
        if errors:
            counts["failed"] += 1
            log.warning("record_partly_added", record_id=hit["id"], errors=errors)

    log.info("subject_communities_synced", **counts)
    return counts
