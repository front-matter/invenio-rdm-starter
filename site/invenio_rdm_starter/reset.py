"""Delete every record, to start a demo instance afresh.

The Starter's demo keeps no data of its own: its records are imported from
the commonmeta store, and imported again at will. Starting afresh means
emptying it of records, but not of what was set up around them: users,
communities, vocabularies, pages, jobs.

InvenioRDM has no way to remove a record: deleting one leaves a tombstone,
and purging isn't implemented. So this removes the records where they are
kept, in one transaction:

- the records, their drafts, parents and versions, and the rows that hang off
  them (files, community inclusions, quotas, secret links, access tokens);
- the requests about a record (deletion, community inclusion), their events
  and files;
- the records' and those requests' buckets, with their objects;
- the records' and parents' PIDs: recid, oai and doi;

and then empties the records' and drafts' search indices.

It refuses unless ``STARTER_DELETE_ALL_RECORDS_ENABLED`` is set, and when any
DOI was minted here: only external DOIs, registered elsewhere, can go without
a trace at a registration agency. Files of the removed buckets stay in
storage; the demo's imports have none.
"""

from __future__ import annotations

from typing import Any

import structlog
from celery import shared_task
from flask import current_app
from sqlalchemy import text

from .exceptions import RecordDeletionRefusedError

#: The PID types of records and their parents.
RECORD_PID_TYPES = ("recid", "oai", "doi")

#: The buckets of records, drafts and record requests, collected before their
#: rows go.
_COLLECT_BUCKETS = """
CREATE TEMP TABLE starter_reset_buckets ON COMMIT DROP AS
  SELECT bucket_id AS id FROM rdm_records_metadata
  UNION SELECT media_bucket_id FROM rdm_records_metadata
  UNION SELECT bucket_id FROM rdm_drafts_metadata
  UNION SELECT media_bucket_id FROM rdm_drafts_metadata
  UNION SELECT bucket_id FROM request_metadata
    WHERE json->'topic'->>'record' IS NOT NULL
"""

_RECORD_REQUESTS = (
    "SELECT id FROM request_metadata WHERE json->'topic'->>'record' IS NOT NULL"
)

_PIDS = "SELECT id FROM pidstore_pid WHERE pid_type IN ('recid', 'oai', 'doi')"

_BUCKETS = "SELECT id FROM starter_reset_buckets WHERE id IS NOT NULL"

#: What the reset deletes, in an order the foreign keys allow.
DELETE_STATEMENTS = (
    "DELETE FROM rdm_versions_state",
    "DELETE FROM rdm_parents_community",
    "DELETE FROM rdm_records_quota",
    "DELETE FROM rdm_records_files",
    "DELETE FROM rdm_records_media_files",
    "DELETE FROM rdm_drafts_files",
    "DELETE FROM rdm_drafts_media_files",
    "DELETE FROM rdm_records_files_version",
    "DELETE FROM rdm_records_media_files_version",
    "DELETE FROM rdm_records_metadata_version",
    "DELETE FROM rdm_records_secret_links",
    "DELETE FROM rdm_records_access_request_tokens",
    "DELETE FROM rdm_drafts_metadata",
    "DELETE FROM rdm_records_metadata",
    "DELETE FROM rdm_parents_metadata",
    f"DELETE FROM request_events WHERE request_id IN ({_RECORD_REQUESTS})",
    f"DELETE FROM request_files WHERE record_id IN ({_RECORD_REQUESTS})",
    "DELETE FROM request_metadata WHERE json->'topic'->>'record' IS NOT NULL",
    f"DELETE FROM files_multipartobject WHERE bucket_id IN ({_BUCKETS})",
    f"DELETE FROM files_object WHERE bucket_id IN ({_BUCKETS})",
    f"DELETE FROM files_buckettags WHERE bucket_id IN ({_BUCKETS})",
    f"DELETE FROM files_bucket WHERE id IN ({_BUCKETS})",
    f"DELETE FROM pidstore_redirect WHERE pid_id IN ({_PIDS})",
    "DELETE FROM pidstore_pid WHERE pid_type IN ('recid', 'oai', 'doi')",
)

#: What a run counts, before it deletes.
_COUNTS = {
    "records": "SELECT count(*) FROM rdm_records_metadata",
    "drafts": "SELECT count(*) FROM rdm_drafts_metadata",
    "parents": "SELECT count(*) FROM rdm_parents_metadata",
    "requests": "SELECT count(*) FROM request_metadata"
    " WHERE json->'topic'->>'record' IS NOT NULL",
    "pids": "SELECT count(*) FROM pidstore_pid"
    " WHERE pid_type IN ('recid', 'oai', 'doi')",
    "minted_dois": "SELECT count(*) FROM pidstore_pid"
    " WHERE pid_type = 'doi' AND coalesce(pid_provider, '') <> 'external'",
}


def count(session: Any) -> dict[str, int]:
    """How many records, drafts, parents, requests and PIDs there are."""
    return {
        name: int(session.execute(text(query)).scalar() or 0)
        for name, query in _COUNTS.items()
    }


def refusal(enabled: bool, counts: dict[str, int]) -> str | None:
    """Why the records can't be deleted here, or ``None`` if they can."""
    if not enabled:
        return (
            "deleting all records is switched off; set "
            "STARTER_DELETE_ALL_RECORDS_ENABLED on an instance that keeps no data"
        )
    if counts["minted_dois"]:
        return (
            f"{counts['minted_dois']} DOIs were minted here; deleting their "
            "records would leave them registered without a record"
        )
    return None


def delete_rows(session: Any) -> None:
    """Delete the records' rows, in one transaction."""
    try:
        session.execute(text(_COLLECT_BUCKETS))
        for statement in DELETE_STATEMENTS:
            session.execute(text(statement))
        session.commit()
    except Exception:
        session.rollback()
        raise


def empty_indices(client: Any, aliases: list[str]) -> dict[str, int]:
    """Delete every document of the records' and drafts' indices."""
    deleted = {}
    for alias in aliases:
        response = client.delete_by_query(
            index=alias,
            body={"query": {"match_all": {}}},
            conflicts="proceed",
            refresh=True,
        )
        if response.get("failures"):
            raise RuntimeError(f"emptying {alias} failed: {response['failures'][:3]}")
        deleted[alias] = int(response.get("deleted") or 0)
    return deleted


def _record_aliases() -> list[str]:
    from invenio_rdm_records.proxies import current_rdm_records

    service = current_rdm_records.records_service
    return [
        service.record_cls.index.search_alias,
        service.draft_cls.index.search_alias,
    ]


@shared_task(ignore_result=False)
def delete_all_records(dry_run: bool = True) -> dict[str, Any]:
    """Delete every record, its drafts, parents, requests and PIDs.

    ``dry_run`` only counts. Refuses (raises) unless
    ``STARTER_DELETE_ALL_RECORDS_ENABLED`` is set, and when a DOI was minted
    here.
    """
    from invenio_db import db
    from invenio_search import current_search_client

    log = structlog.get_logger().bind(service="invenio-rdm-starter", dry_run=dry_run)
    counts = count(db.session)
    reason = refusal(
        bool(current_app.config.get("STARTER_DELETE_ALL_RECORDS_ENABLED")), counts
    )
    if reason:
        log.error("records_deletion_refused", reason=reason, **counts)
        raise RecordDeletionRefusedError(reason)
    if dry_run:
        log.warning("records_deletion_dry_run", **counts)
        return counts

    delete_rows(db.session)
    emptied = empty_indices(current_search_client, _record_aliases())
    log.warning("records_deleted", **counts, indexed_deleted=emptied)
    return {**counts, "index_documents_deleted": emptied}
