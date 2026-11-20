"""Deleting all records, to start a demo instance afresh."""

from __future__ import annotations

import re
from importlib.metadata import entry_points

import invenio_communities.communities.records.models  # noqa: F401
import invenio_files_rest.models  # noqa: F401
import invenio_pidstore.models  # noqa: F401
import invenio_rdm_records.records.models  # noqa: F401
import invenio_requests.records.models  # noqa: F401
import pytest
from invenio_db import db
from invenio_rdm_starter import jobs, reset

RECORD_TABLES = {"rdm_records_metadata", "rdm_drafts_metadata", "rdm_parents_metadata"}


def _deleted_tables() -> list[str]:
    return [
        re.match(r"DELETE FROM (\w+)", statement).group(1)
        for statement in reset.DELETE_STATEMENTS
    ]


def test_every_deleted_table_exists():
    # The *_version tables are SQLAlchemy-Continuum's, made when an app with
    # versioning (InvenioRDM's default) starts, not by importing the models.
    tables = {name for name in _deleted_tables() if not name.endswith("_version")}

    assert tables <= set(db.metadata.tables)


@pytest.mark.parametrize("target", sorted(RECORD_TABLES) + ["pidstore_pid"])
def test_what_refers_to_a_row_goes_before_it(target):
    """InvenioRDM's own models say which tables point at the records."""
    order = _deleted_tables()
    referring = {
        table.name
        for table in db.metadata.tables.values()
        for key in table.foreign_keys
        if key.column.table.name == target and table.name != target
    }

    assert target in order
    for table in referring:
        assert table in order, f"{table} refers to {target}"
        assert order.index(table) < order.index(target)


def test_the_buckets_go_after_what_is_in_them():
    order = _deleted_tables()
    bucket_rows = {
        table.name
        for table in db.metadata.tables.values()
        for key in table.foreign_keys
        if key.column.table.name == "files_bucket"
    }
    # A community's logo bucket isn't a record's: communities stay.
    for table in bucket_rows - {"communities_metadata"}:
        assert table in order
        assert order.index(table) < order.index("files_bucket")


def test_only_record_buckets_and_pids_go():
    statements = " ".join(reset.DELETE_STATEMENTS)

    assert "DELETE FROM files_bucket WHERE id IN" in statements
    assert "DELETE FROM pidstore_pid WHERE pid_type IN ('recid', 'oai', 'doi')" in (
        statements
    )
    assert "communities_metadata" not in statements
    assert "accounts_user" not in statements


COUNTS = {
    "records": 2388,
    "drafts": 1376,
    "parents": 2383,
    "requests": 0,
    "pids": 7536,
    "minted_dois": 0,
}


@pytest.mark.parametrize(
    ("enabled", "counts", "refused"),
    [
        (True, COUNTS, None),
        (False, COUNTS, "switched off"),
        (True, {**COUNTS, "minted_dois": 3}, "3 DOIs were minted here"),
    ],
)
def test_it_refuses_unless_switched_on_and_without_minted_dois(
    enabled, counts, refused
):
    reason = reset.refusal(enabled, counts)

    if refused is None:
        assert reason is None
    else:
        assert refused in reason


class SearchClient:
    """OpenSearch, answering delete_by_query."""

    def __init__(self, failures=None):
        self.failures = failures or []
        self.calls = []

    def delete_by_query(self, index, body, conflicts, refresh):
        self.calls.append(index)
        return {"deleted": 7, "failures": self.failures}


def test_the_record_indices_are_emptied():
    client = SearchClient()

    deleted = reset.empty_indices(client, ["rdmrecords-records", "rdmrecords-drafts"])

    assert deleted == {"rdmrecords-records": 7, "rdmrecords-drafts": 7}
    assert client.calls == ["rdmrecords-records", "rdmrecords-drafts"]


def test_a_failed_index_deletion_is_an_error():
    with pytest.raises(RuntimeError, match="emptying rdmrecords-records failed"):
        reset.empty_indices(
            SearchClient(failures=[{"id": "x"}]), ["rdmrecords-records"]
        )


def test_the_job_starts_as_a_dry_run():
    assert jobs.DeleteAllRecordsJob.build_task_arguments(None) == {"dry_run": True}
    assert jobs.DeleteAllRecordsJob.build_task_arguments(None, dry_run=False) == {
        "dry_run": False
    }


def test_the_job_and_its_task_are_registered():
    registered = {ep.name: ep.value for ep in entry_points(group="invenio_jobs.jobs")}
    tasks = {ep.name: ep.value for ep in entry_points(group="invenio_celery.tasks")}

    assert registered["starter_delete_all_records"] == (
        "invenio_rdm_starter.jobs:DeleteAllRecordsJob"
    )
    assert tasks["invenio_rdm_starter_reset"] == "invenio_rdm_starter.reset"


def test_the_aliases_carry_the_index_prefix(monkeypatch):
    """The error of the first run on demo: no such index [rdmrecords-records]."""
    from flask import Flask

    app = Flask(__name__)
    app.config["SEARCH_INDEX_PREFIX"] = "invenio-rdm-"
    index = type("Index", (), {"search_alias": "rdmrecords-records"})
    drafts = type("Index", (), {"search_alias": "rdmrecords-drafts"})
    service = type(
        "Service",
        (),
        {
            "record_cls": type("R", (), {"index": index}),
            "draft_cls": type("D", (), {"index": drafts}),
        },
    )
    proxy = type("Proxy", (), {"records_service": service})
    monkeypatch.setattr(
        "invenio_rdm_records.proxies.current_rdm_records", proxy, raising=False
    )

    with app.app_context():
        aliases = reset._record_aliases()

    assert aliases == [
        "invenio-rdm-rdmrecords-records",
        "invenio-rdm-rdmrecords-drafts",
    ]
