"""Tests for the OpenAlex subfield communities."""

from collections import Counter
from datetime import UTC, datetime
from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest
from invenio_rdm_starter.jobs import (
    AddRecordsToSubjectCommunitiesJob,
    CreateSubjectCommunitiesJob,
)
from invenio_rdm_starter.subject_communities import (
    add_records_to_subject_communities,
    community_data,
    create_subject_communities,
    feature_subject_communities,
    record_subfields,
    subfield_slug,
)

SUBFIELD = "https://openalex.org/subfields/"


@pytest.mark.parametrize(
    ("subjects", "expected"),
    [
        pytest.param(
            [{"id": f"{SUBFIELD}1311", "subject": "Genetics", "scheme": "Subfields"}],
            {"1311": "Genetics"},
            id="subfield",
        ),
        pytest.param(
            [
                {"id": f"{SUBFIELD}1311", "subject": "Genetics"},
                {"id": "https://openalex.org/fields/13", "subject": "Biochemistry"},
                {"id": "https://openalex.org/T10017", "subject": "A topic"},
                {"subject": "Genetics"},
            ],
            {"1311": "Genetics"},
            id="only subfields, not fields, topics or keywords",
        ),
        pytest.param(
            [{"id": f"{SUBFIELD}3309"}],
            {"3309": "3309"},
            id="no name yet",
        ),
        pytest.param([{"id": f"{SUBFIELD}abc"}], {}, id="not a subfield number"),
        pytest.param(None, {}, id="no subjects"),
    ],
)
def test_record_subfields(subjects, expected):
    assert record_subfields({"metadata": {"subjects": subjects}}) == expected


def test_a_subject_community_is_named_and_typed_like_rogue_scholars():
    data = community_data("3309", "Library and Information Sciences")

    assert data["slug"] == "3309"
    assert data["metadata"] == {
        "title": "Library and Information Sciences",
        "type": {"id": "subject"},
        "website": "https://openalex.org/subfields/3309",
    }
    assert data["access"]["visibility"] == "public"


@pytest.mark.parametrize(
    ("subject_id", "slug"),
    [
        (f"{SUBFIELD}3309", "3309"),
        (f"{SUBFIELD}3309/", "3309"),
        ("https://openalex.org/fields/33", None),
        ("https://openalex.org/T10017", None),
        (f"{SUBFIELD}abc", None),
        ("", None),
    ],
)
def test_subfield_slug(subject_id, slug):
    assert subfield_slug(subject_id) == slug


@pytest.mark.parametrize(
    ("job", "task"),
    [
        (CreateSubjectCommunitiesJob, create_subject_communities),
        (AddRecordsToSubjectCommunitiesJob, add_records_to_subject_communities),
    ],
)
def test_each_job_runs_its_task_over_everything(job, task):
    assert job.task is task
    assert job.build_task_arguments(None, since="2026-01-01") == {}


@pytest.mark.parametrize(
    ("group", "name", "value"),
    [
        (
            "invenio_jobs.jobs",
            "starter_create_subject_communities",
            "invenio_rdm_starter.jobs:CreateSubjectCommunitiesJob",
        ),
        (
            "invenio_jobs.jobs",
            "starter_add_records_to_subject_communities",
            "invenio_rdm_starter.jobs:AddRecordsToSubjectCommunitiesJob",
        ),
        (
            "invenio_celery.tasks",
            "invenio_rdm_starter",
            "invenio_rdm_starter.subject_communities",
        ),
    ],
)
def test_the_job_and_its_task_are_registered(group, name, value):
    """Without them the dashboard doesn't list a job, or Celery can't run it."""
    registered = {ep.name: ep.value for ep in entry_points(group=group)}

    assert registered.get(name) == value


class Communities:
    """The communities service: its featured entries."""

    def __init__(self, featured=0, failing=()):
        self.featured = featured
        self.failing = set(failing)
        self.created = []

    def featured_search(self, identity, params):
        return SimpleNamespace(total=self.featured)

    def featured_create(self, identity, community_id, data):
        if community_id in self.failing:
            raise ValueError("no such community")
        self.created.append((community_id, data["start_date"]))


def test_the_largest_communities_are_featured_from_now():
    communities = Communities()
    members = Counter({"stats": 316, "ai": 276, "software": 242, "biology": 221})

    assert feature_subject_communities(communities, members, 3) == 3
    assert [cid for cid, _start in communities.created] == ["stats", "ai", "software"]
    start = datetime.fromisoformat(communities.created[0][1])
    assert abs((datetime.now(UTC) - start).total_seconds()) < 60


def test_communities_an_admin_featured_are_left_as_they_are():
    communities = Communities(featured=2)

    assert feature_subject_communities(communities, Counter({"stats": 316}), 5) == 0
    assert communities.created == []


@pytest.mark.parametrize(
    ("members", "count"), [(Counter({"stats": 1}), 0), (Counter(), 5)]
)
def test_nothing_is_featured_without_a_count_or_records(members, count):
    communities = Communities()

    assert feature_subject_communities(communities, members, count) == 0
    assert communities.created == []


def test_one_community_failing_leaves_the_others_featured():
    communities = Communities(failing={"ai"})

    assert (
        feature_subject_communities(communities, Counter({"stats": 2, "ai": 1}), 2) == 1
    )
    assert communities.created[0][0] == "stats"
