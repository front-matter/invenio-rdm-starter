"""Tests for the OpenAlex subfield communities."""

from importlib.metadata import entry_points

import pytest
from invenio_rdm_starter.jobs import SubjectCommunitiesJob
from invenio_rdm_starter.subject_communities import (
    community_data,
    record_subfields,
    sync_subject_communities,
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


def test_the_job_runs_the_sweep_over_every_record():
    assert SubjectCommunitiesJob.task is sync_subject_communities
    assert SubjectCommunitiesJob.build_task_arguments(None, since="2026-01-01") == {}


@pytest.mark.parametrize(
    ("group", "name", "value"),
    [
        (
            "invenio_jobs.jobs",
            "starter_subject_communities",
            "invenio_rdm_starter.jobs:SubjectCommunitiesJob",
        ),
        (
            "invenio_celery.tasks",
            "invenio_rdm_starter",
            "invenio_rdm_starter.subject_communities",
        ),
    ],
)
def test_the_job_and_its_task_are_registered(group, name, value):
    """Without them the dashboard doesn't list the job, or Celery can't run it."""
    registered = {ep.name: ep.value for ep in entry_points(group=group)}

    assert registered.get(name) == value
