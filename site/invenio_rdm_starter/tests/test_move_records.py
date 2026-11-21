"""Tests for moving records between Starter Packs' communities."""

from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest
from invenio_rdm_starter import starter_packs
from invenio_rdm_starter.jobs import (
    MoveRecordsArgsSchema,
    MoveRecordsToStarterPackJob,
    StarterPackSlug,
)
from marshmallow import ValidationError

PACKS = {"joss": "c-joss", "rogue-scholar": "c-rogue", "arxiv-cs-dl": "c-arxiv"}


def _hit(record_id, *community_ids):
    return {"id": record_id, "parent": {"communities": {"ids": list(community_ids)}}}


class Records:
    def __init__(self, hits):
        self.hits = hits
        self.queries = []

    def scan(self, identity, params):
        self.queries.append(params["q"])
        return SimpleNamespace(hits=iter(self.hits))


class RecordCommunities:
    def __init__(self, failing=(), present=()):
        self.calls = []
        self.failing = set(failing)
        self.present = set(present)

    def bulk_add(self, identity, community_id, record_ids):
        self.calls.append(("bulk_add", tuple(record_ids), community_id))
        errors = [
            {"record_id": id_, "message": "Community already included."}
            for id_ in record_ids
            if id_ in self.present
        ]
        errors += [
            {"record_id": id_, "message": "refused"}
            for id_ in record_ids
            if id_ in self.failing
        ]
        return errors

    def remove(self, identity, id_, data):
        self.calls.append(("remove", id_, data["communities"][0]["id"]))
        return [], []


@pytest.mark.parametrize(
    ("source", "query"),
    [
        ("joss", 'parent.communities.ids:"c-joss"'),
        (
            None,
            'NOT parent.communities.ids:("c-joss" OR "c-rogue" OR "c-arxiv")',
        ),
    ],
)
def test_the_records_of_a_pack_or_of_none(source, query):
    assert starter_packs.selection_query(PACKS, source) == query


def test_without_packs_every_record_is_in_none():
    assert starter_packs.selection_query({}, None) == "*"


@pytest.mark.parametrize(
    ("source", "target", "reason"),
    [
        ("joss", "joss", "the same"),
        (None, "", "the same"),
        ("joss", "zenodo", "zenodo is not a Starter Pack"),
        ("subject", None, "subject is not a Starter Pack"),
    ],
)
def test_what_is_no_move_is_refused(source, target, reason):
    with pytest.raises(starter_packs.MoveError, match=reason):
        starter_packs.move_records(
            Records([]), RecordCommunities(), PACKS, source, target
        )


def test_a_dry_run_only_counts():
    records = Records([_hit("a"), _hit("b", "c-subject")])
    communities = RecordCommunities()

    counts = starter_packs.move_records(records, communities, PACKS, None, "joss")

    assert counts == {
        "source": "",
        "target": "joss",
        "dry_run": True,
        "records": 2,
        "moved": 0,
        "failed": 0,
    }
    assert communities.calls == []


def test_records_in_no_pack_join_the_target():
    records = Records([_hit("a"), _hit("b", "c-subject")])
    communities = RecordCommunities()

    counts = starter_packs.move_records(
        records, communities, PACKS, None, "joss", dry_run=False
    )

    assert counts["moved"] == 2
    # In bulk, without inclusion requests and so without notifications.
    assert communities.calls == [("bulk_add", ("a", "b"), "c-joss")]


def test_the_records_are_added_in_batches():
    records = Records([_hit(id_) for id_ in "abcde"])
    communities = RecordCommunities()

    counts = starter_packs.move_records(
        records, communities, PACKS, None, "joss", dry_run=False, batch_size=2
    )

    assert counts["moved"] == 5
    assert [call[1] for call in communities.calls] == [
        ("a", "b"),
        ("c", "d"),
        ("e",),
    ]


def test_a_record_in_the_target_already_is_moved_still():
    records = Records([_hit("a", "c-joss")])
    communities = RecordCommunities(present={"a"})

    counts = starter_packs.move_records(
        records, communities, PACKS, "joss", "rogue-scholar", dry_run=False
    )

    assert (counts["moved"], counts["failed"]) == (1, 0)
    assert communities.calls[-1] == ("remove", "a", "c-joss")


def test_a_record_joins_the_target_before_it_leaves_the_source():
    records = Records([_hit("a", "c-joss", "c-subject")])
    communities = RecordCommunities()

    starter_packs.move_records(
        records, communities, PACKS, "joss", "rogue-scholar", dry_run=False
    )

    assert communities.calls == [
        ("bulk_add", ("a",), "c-rogue"),
        ("remove", "a", "c-joss"),
    ]


def test_without_a_target_the_records_leave_their_pack():
    records = Records([_hit("a", "c-joss")])
    communities = RecordCommunities()

    starter_packs.move_records(records, communities, PACKS, "joss", None, dry_run=False)

    assert communities.calls == [("remove", "a", "c-joss")]


def test_a_record_not_added_stays_where_it_was():
    records = Records([_hit("a", "c-joss"), _hit("b", "c-joss")])
    communities = RecordCommunities(failing={"a"})

    counts = starter_packs.move_records(
        records, communities, PACKS, "joss", "arxiv-cs-dl", dry_run=False
    )

    assert (counts["moved"], counts["failed"]) == (1, 1)
    assert ("remove", "a", "c-joss") not in communities.calls


def test_the_job_starts_as_a_dry_run():
    build = MoveRecordsToStarterPackJob.build_task_arguments

    assert build(None) == {"dry_run": True, "source_slug": None, "target_slug": None}
    assert build(None, dry_run=False, source_slug="", target_slug="joss") == {
        "dry_run": False,
        "source_slug": None,
        "target_slug": "joss",
    }


def test_the_packs_are_a_select_with_none_first(monkeypatch):
    monkeypatch.setattr(StarterPackSlug, "_slugs", staticmethod(lambda: sorted(PACKS)))

    assert StarterPackSlug().choices == ["", "arxiv-cs-dl", "joss", "rogue-scholar"]


def test_the_form_refuses_the_same_pack_twice(monkeypatch):
    monkeypatch.setattr(StarterPackSlug, "_slugs", staticmethod(lambda: sorted(PACKS)))
    schema = MoveRecordsArgsSchema()

    with pytest.raises(ValidationError, match="the same"):
        schema.load({"source_slug": "joss", "target_slug": "joss"})
    with pytest.raises(ValidationError, match="not a Starter Pack"):
        schema.load({"source_slug": "zenodo", "target_slug": "joss"})
    assert schema.load({"target_slug": "joss"})["dry_run"] is True


def test_the_job_is_registered():
    jobs = {ep.name: ep.value for ep in entry_points(group="invenio_jobs.jobs")}

    assert (
        jobs["starter_move_records_to_starter_pack"]
        == "invenio_rdm_starter.jobs:MoveRecordsToStarterPackJob"
    )


def test_the_records_are_read_before_any_is_moved():
    """The scan's search context lasts minutes between pages."""
    events = []

    class ReadRecords:
        def scan(self, identity, params):
            def hits():
                for record_id in "ab":
                    events.append(("read", record_id))
                    yield _hit(record_id)
                events.append(("scan done",))

            return SimpleNamespace(hits=hits())

    class Communities(RecordCommunities):
        def bulk_add(self, identity, community_id, record_ids):
            events.append(("add",))
            return []

    starter_packs.move_records(
        ReadRecords(), Communities(), PACKS, None, "joss", dry_run=False, batch_size=1
    )

    assert events.index(("scan done",)) < events.index(("add",))
