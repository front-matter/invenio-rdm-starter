"""Tests for the Starter Packs, communities of type starterpack."""

from datetime import UTC, datetime
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

    assert [pack["slug"] for pack in packs] == ["irights", "joss"]
    assert all(pack["website"].startswith("https://") for pack in packs)
    fields = {pack["slug"]: starter_packs.custom_fields(pack) for pack in packs}
    assert fields == {
        "irights": {
            "rs:doi": "10.59350/irights",
            "rs:language": {"id": "deu"},
            "rs:license": {"id": "cc-by-4.0"},
        },
        "joss": {
            "rs:issn": "2475-9066",
            "rs:prefix": "10.21105",
            "rs:language": {"id": "eng"},
            "rs:license": {"id": "cc-by-4.0"},
        },
    }


def test_the_packs_fields_are_the_communities_custom_fields():
    """Each field a pack gives is one the communities have, in rs."""
    from invenio_rdm_starter import config

    defined = {field.name for field in config.COMMUNITIES_CUSTOM_FIELDS}
    packs = starter_packs.load_packs(APP_DATA / "starter_packs.yaml")

    assert config.COMMUNITIES_NAMESPACES == {"rs": None}
    assert defined == {
        "rs:issn",
        "rs:doi",
        "rs:prefix",
        "rs:language",
        "rs:license",
    }
    assert {name for pack in packs for name in pack["custom_fields"]} <= defined
    ui = {f["field"] for f in config.COMMUNITIES_CUSTOM_FIELDS_UI[0]["fields"]}
    assert ui == defined


def test_a_communitys_vocabulary_field_takes_the_dereferenced_entry():
    """A license is indexed with its props and icon."""
    from invenio_rdm_starter import config

    license_ = next(
        f for f in config.COMMUNITIES_CUSTOM_FIELDS if f.name == "rs:license"
    )
    properties = license_.mapping["properties"]

    assert properties["props"] == {"type": "object", "dynamic": "true"}
    assert properties["icon"] == {"type": "keyword"}


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
            "custom_fields": {"rs:issn": "2475-9066", "rs:license": "cc-by-4.0"},
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
        "custom_fields": {"rs:issn": "2475-9066", "rs:license": {"id": "cc-by-4.0"}},
    }
    assert data["access"]["record_submission_policy"] == "closed"


class Service:
    """A service that holds some ids, and records what it creates."""

    def __init__(self, existing=(), failing=(), featured=()):
        self.existing = set(existing)
        self.failing = set(failing)
        self.created = []
        self.featured = {id_: ["earlier"] for id_ in featured}

    def read(self, identity, id_):
        if id_ not in self.existing:
            raise PIDDoesNotExistError("x", id_)
        return SimpleNamespace(id=f"id-{id_}")

    def create(self, identity, data):
        key = data.get("slug") or data["id"]
        if key in self.failing:
            raise ValueError("refused")
        self.created.append(data)
        return SimpleNamespace(id=f"id-{key}")

    logos: dict = None

    def read_logo(self, identity, community_id):
        from invenio_communities.errors import LogoNotFoundError

        if community_id not in (self.logos or {}):
            raise LogoNotFoundError()
        return self.logos[community_id]

    def update_logo(self, identity, community_id, stream, content_length=None):
        self.logos = self.logos or {}
        self.logos[community_id] = (stream.read(), content_length)

    def featured_list(self, identity, community_id):
        return SimpleNamespace(total=len(self.featured.get(community_id, [])))

    def featured_create(self, identity, community_id, data):
        self.featured.setdefault(community_id, []).append(data["start_date"])


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
        "featured": 2,
        "logos": 0,
        "failed": 1,
        "type_created": 1,
    }
    assert [c["slug"] for c in communities.created] == ["rogue-scholar"]
    # Created or there already, each pack is featured.
    assert set(communities.featured) == {"id-rogue-scholar", "id-joss"}
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


def test_a_featured_pack_is_not_featured_again():
    communities = Service(existing={"joss"}, featured={"id-joss"})

    counts = starter_packs.create_packs(communities, Service(), PACKS[1:2])

    assert counts["featured"] == 0
    assert communities.featured["id-joss"] == ["earlier"]


def test_a_pack_is_featured_from_now():
    communities = Service()

    starter_packs.create_packs(communities, Service(), PACKS[:1])

    (start,) = communities.featured["id-rogue-scholar"]
    assert abs((datetime.now(UTC) - datetime.fromisoformat(start)).total_seconds()) < 60


def test_the_packs_logos_are_in_app_data_and_small_enough():
    """InvenioRDM refuses a community logo over 1 MB."""
    for pack in starter_packs.load_packs(APP_DATA / "starter_packs.yaml"):
        logo = APP_DATA / pack["logo"]

        assert logo.is_file(), logo
        assert logo.stat().st_size <= 10**6, logo


def test_a_pack_gets_its_logo_while_it_has_none(tmp_path):
    (tmp_path / "joss.png").write_bytes(b"PNG")
    communities = Service()
    pack = {"slug": "joss", "title": "JOSS", "logo": "joss.png"}

    counts = starter_packs.create_packs(communities, Service(), [pack], tmp_path)

    assert counts["logos"] == 1
    assert communities.logos == {"id-joss": (b"PNG", 3)}

    # An admin's logo stays.
    communities.logos["id-joss"] = (b"ADMIN", 5)
    communities.existing.add("joss")
    counts = starter_packs.create_packs(communities, Service(), [pack], tmp_path)

    assert counts["logos"] == 0
    assert communities.logos == {"id-joss": (b"ADMIN", 5)}
