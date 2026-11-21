"""Tests for the Starter Packs, communities of type starterpack."""

from importlib.metadata import entry_points
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from invenio_pidstore.errors import PIDDoesNotExistError
from invenio_rdm_starter import starter_packs
from invenio_rdm_starter.jobs import CreateStarterPackCommunitiesJob

APP_DATA = Path(__file__).parents[3] / "app_data"


def test_the_three_starter_packs_are_defined():
    packs = starter_packs.load_packs(APP_DATA / "starter_packs.yaml")

    assert [pack["slug"] for pack in packs] == ["rogue-scholar", "joss", "arxiv-cs-dl"]
    assert all(pack["website"].startswith("https://") for pack in packs)


def test_the_starterpack_type_is_in_the_vocabulary_fixtures():
    """With the title the job gives it on an instance set up before it."""
    types = yaml.safe_load(
        (APP_DATA / "vocabularies" / "community_types.yaml").read_text()
    )
    entry = next(t for t in types if t["id"] == "starterpack")

    assert entry["title"] == starter_packs.COMMUNITY_TYPE_TITLE


def test_a_pack_without_a_slug_is_refused(tmp_path):
    path = tmp_path / "packs.yaml"
    path.write_text("- title: No slug\n")

    with pytest.raises(starter_packs.StarterPackError, match="slug and a title"):
        starter_packs.load_packs(path)


def test_a_pack_becomes_a_curated_starterpack_community():
    data = starter_packs.community_data(
        {
            "slug": "joss",
            "title": "Journal of Open Source Software",
            "description": "Papers about research software.\n",
            "website": "https://joss.theoj.org",
        }
    )

    assert data == {
        "slug": "joss",
        "access": starter_packs.COMMUNITY_ACCESS,
        "metadata": {
            "title": "Journal of Open Source Software",
            "type": {"id": "starterpack"},
            "description": "Papers about research software.",
            "website": "https://joss.theoj.org",
        },
    }
    assert data["access"]["record_submission_policy"] == "closed"


class Service:
    """A service that holds some ids, and records what it creates."""

    def __init__(self, existing=(), failing=()):
        self.existing = set(existing)
        self.failing = set(failing)
        self.created = []

    def read(self, identity, id_):
        if id_ not in self.existing:
            raise PIDDoesNotExistError("x", id_)
        return SimpleNamespace(id=id_)

    def create(self, identity, data):
        key = data.get("slug") or data["id"]
        if key in self.failing:
            raise ValueError("refused")
        self.created.append(data)


PACKS = [
    {"slug": "rogue-scholar", "title": "Rogue Scholar"},
    {"slug": "joss", "title": "JOSS"},
    {"slug": "arxiv-cs-dl", "title": "arXiv cs.DL"},
]


def test_the_missing_packs_and_their_type_are_created():
    communities = Service(existing={"joss"}, failing={"arxiv-cs-dl"})
    vocabularies = Service()

    counts = starter_packs.create_packs(communities, vocabularies, PACKS)

    assert counts == {
        "packs": 3,
        "existing": 1,
        "created": 1,
        "failed": 1,
        "type_created": 1,
    }
    assert [c["slug"] for c in communities.created] == ["rogue-scholar"]
    assert vocabularies.created == [
        {
            "id": "starterpack",
            "title": starter_packs.COMMUNITY_TYPE_TITLE,
            "type": "communitytypes",
        }
    ]


def test_a_type_the_vocabulary_has_is_kept():
    vocabularies = Service(existing={("communitytypes", "starterpack")})

    counts = starter_packs.create_packs(Service(), vocabularies, PACKS[:1])

    assert counts["type_created"] == 0
    assert vocabularies.created == []


def test_the_job_runs_its_task_and_is_registered():
    assert (
        CreateStarterPackCommunitiesJob.task
        is starter_packs.create_starter_pack_communities
    )
    assert CreateStarterPackCommunitiesJob.build_task_arguments(None) == {}
    jobs = {ep.name: ep.value for ep in entry_points(group="invenio_jobs.jobs")}
    tasks = {ep.name: ep.value for ep in entry_points(group="invenio_celery.tasks")}

    assert (
        jobs["starter_create_starter_pack_communities"]
        == "invenio_rdm_starter.jobs:CreateStarterPackCommunitiesJob"
    )
    assert tasks["invenio_rdm_starter_packs"] == "invenio_rdm_starter.starter_packs"
