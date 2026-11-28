"""Tests for the Starter Packs, communities of a journal, an organization, …"""

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

    assert [pack["slug"] for pack in packs] == ["joss", "mhh", "wellcome", "rzepa"]
    assert all(pack["website"].startswith("https://") for pack in packs)
    assert [pack["type"] for pack in packs] == [
        "journal",
        "organization",
        "funder",
        "blog",
    ]
    fields = {pack["slug"]: starter_packs.custom_fields(pack) for pack in packs}
    assert fields == {
        "joss": {
            "rs:issn": "2475-9066",
            "rs:prefix": "10.21105",
            "rs:language": {"id": "eng"},
            "rs:license": {"id": "cc-by-4.0"},
        },
        "mhh": {
            "rs:language": {"id": "deu"},
        },
        "wellcome": {
            "rs:language": {"id": "eng"},
            "rs:license": {"id": "cc-by-4.0"},
        },
        "rzepa": {
            "rs:doi": "10.59350/rzepa",
            "rs:language": {"id": "eng"},
            "rs:license": {"id": "cc-by-4.0"},
        },
    }
    assert [pack.get("organizations") for pack in packs] == [
        None,
        ["00f2yqf98"],
        ["029chgv08"],
        None,
    ]


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
        "rs:records_view",
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


def test_the_packs_types_are_in_the_vocabulary_fixtures():
    """Journal, repository and funder join Blog; Starter Pack is no type."""
    types = yaml.safe_load(
        (APP_DATA / "vocabularies" / "community_types.yaml").read_text()
    )
    ids = [t["id"] for t in types]

    assert set(starter_packs.PACK_TYPES) <= set(ids)
    for gone in ("starterpack", "subject", "container"):
        assert gone not in ids
    funder = next(t for t in types if t["id"] == "funder")
    assert funder["title"]["de"] == "Förderer"
    # InvenioRDM's own types keep the translations its fixtures give them.
    organization = next(t for t in types if t["id"] == "organization")
    assert {"es", "cs", "ar"} <= set(organization["title"])


def test_an_award_is_a_resource_type_a_record_can_have():
    """InvenioRDM checks a record's resource type for the tag depositable."""
    types = yaml.safe_load(
        (APP_DATA / "vocabularies" / "resource_types.yaml").read_text()
    )
    award = next(t for t in types if t["id"] == "award")

    assert award["props"]["datacite_general"] == "Award"
    assert award["props"]["schema.org"] == "https://schema.org/MonetaryGrant"
    assert award["tags"] == ["depositable", "linkable"]


@pytest.mark.parametrize(
    ("pack", "message"),
    [
        ("- slug: a\n  title: A\n", "type is one of journal, blog, repository"),
        ("- slug: a\n  title: A\n  type: topic\n", "type is one of"),
    ],
)
def test_a_pack_needs_a_type_of_a_pack(tmp_path, pack, message):
    path = tmp_path / "packs.yaml"
    path.write_text(pack)

    with pytest.raises(starter_packs.StarterPackError, match=message):
        starter_packs.load_packs(path)


def test_a_pack_without_a_slug_is_refused(tmp_path):
    path = tmp_path / "packs.yaml"
    path.write_text("- title: No slug\n")

    with pytest.raises(starter_packs.StarterPackError, match="slug and a title"):
        starter_packs.load_packs(path)


def test_a_pack_becomes_a_curated_community_of_its_type():
    data = starter_packs.community_data(
        {
            "slug": "joss",
            "title": "Journal of Open Source Software",
            "type": "journal",
            "description": "Papers about research software.\n",
            "website": "https://joss.theoj.org",
            "organizations": ["https://ror.org/00f2yqf98", "", "03x94j517"],
            "custom_fields": {"rs:issn": "2475-9066", "rs:license": "cc-by-4.0"},
        }
    )

    assert data == {
        "slug": "joss",
        "access": starter_packs.COMMUNITY_ACCESS,
        "metadata": {
            "title": "Journal of Open Source Software",
            "type": {"id": "journal"},
            "description": "Papers about research software.",
            "website": "https://joss.theoj.org",
            "organizations": [{"id": "00f2yqf98"}, {"id": "03x94j517"}],
        },
        "custom_fields": {"rs:issn": "2475-9066", "rs:license": {"id": "cc-by-4.0"}},
    }
    assert data["access"]["record_submission_policy"] == "closed"


class Service:
    """A service that holds some ids, and records what it creates or updates.

    ``data`` gives an existing community's data, as ``to_dict`` returns it.
    """

    def __init__(self, existing=(), failing=(), featured=(), data=None):
        self.existing = set(existing)
        self.failing = set(failing)
        self.created = []
        self.updated = []
        self.featured = {id_: ["earlier"] for id_ in featured}
        self.data = data or {}

    def read(self, identity, id_):
        if id_ not in self.existing:
            raise PIDDoesNotExistError("x", id_)
        data = self.data.get(id_) or {"slug": id_, "metadata": {}}
        return SimpleNamespace(id=f"id-{id_}", to_dict=lambda: data)

    def update(self, identity, id_, data):
        self.updated.append((id_, data))
        return SimpleNamespace(id=id_)

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
    {"slug": "rogue-scholar", "title": "Rogue Scholar", "type": "journal"},
    {"slug": "joss", "title": "JOSS", "type": "journal"},
    {"slug": "arxiv-cs-dl", "title": "arXiv cs.DL", "type": "journal"},
]

TYPES = [
    {"id": "journal", "title": {"en": "Journal"}},
    {"id": "organization", "title": {"en": "Organization"}},
]

AWARD = {
    "id": "award",
    "icon": "award",
    "props": {"datacite_general": "Award"},
    "title": {"en": "Award"},
    "tags": ["depositable", "linkable"],
}


def test_the_missing_packs_and_types_are_created():
    communities = Service(
        existing={"joss"},
        failing={"arxiv-cs-dl"},
        data={
            "joss": {
                "slug": "joss",
                "metadata": {"type": {"id": "journal"}},
            }
        },
    )
    vocabularies = Service(existing={("communitytypes", "organization")})

    counts = starter_packs.create_packs(
        communities,
        vocabularies,
        PACKS,
        vocabulary_entries={"communitytypes": TYPES, "resourcetypes": [AWARD]},
    )

    assert counts == {
        "packs": 3,
        "existing": 1,
        "created": 1,
        "updated": 0,
        "featured": 2,
        "logos": 0,
        "failed": 1,
        "vocabulary_entries_created": 2,
        "vocabulary_entries_updated": 0,
    }
    assert [c["slug"] for c in communities.created] == ["rogue-scholar"]
    # Created or there already, each pack is featured.
    assert set(communities.featured) == {"id-rogue-scholar", "id-joss"}
    assert vocabularies.created == [
        {"id": "journal", "title": {"en": "Journal"}, "type": "communitytypes"},
        {**AWARD, "type": "resourcetypes"},
    ]


def test_an_existing_entry_gets_the_tags_it_lacks():
    """An award added with linkable alone becomes depositable too."""
    before = {
        "id": "award",
        "type": "resourcetypes",
        "icon": "award",
        "props": {"datacite_general": "Award"},
        "title": {"en": "Award", "de": "Förderung, as an admin named it"},
        "tags": ["linkable"],
        "links": {"self": "https://localhost/api/vocabularies/resourcetypes/award"},
        "revision_id": 2,
    }
    vocabularies = Service(
        existing={("resourcetypes", "award")},
        data={("resourcetypes", "award"): before},
    )

    counts = starter_packs.create_packs(
        Service(), vocabularies, [], vocabulary_entries={"resourcetypes": [AWARD]}
    )

    assert counts["vocabulary_entries_created"] == 0
    assert counts["vocabulary_entries_updated"] == 1
    assert vocabularies.created == []
    ((id_, data),) = vocabularies.updated
    assert id_ == ("resourcetypes", "award")
    assert data == {
        "id": "award",
        "type": "resourcetypes",
        "icon": "award",
        "props": {"datacite_general": "Award"},
        # What an admin edited stays.
        "title": {"en": "Award", "de": "Förderung, as an admin named it"},
        "tags": ["linkable", "depositable"],
    }


def test_an_entry_with_the_tags_already_is_left_alone():
    vocabularies = Service(
        existing={("resourcetypes", "award")},
        data={
            ("resourcetypes", "award"): {**AWARD, "tags": ["linkable", "depositable"]}
        },
    )

    counts = starter_packs.create_packs(
        Service(), vocabularies, [], vocabulary_entries={"resourcetypes": [AWARD]}
    )

    assert counts["vocabulary_entries_updated"] == 0
    assert vocabularies.updated == []


def test_an_existing_community_takes_its_packs_type():
    """joss, a community of type starterpack, becomes a journal."""
    before = {
        "slug": "joss",
        "access": {"visibility": "public"},
        "metadata": {
            "title": "JOSS, as an admin named it",
            "type": {"id": "starterpack", "title": {"en": "Starter Pack"}},
        },
        "custom_fields": {"rs:issn": "2475-9066"},
    }
    communities = Service(existing={"joss"}, data={"joss": before})

    counts = starter_packs.create_packs(communities, Service(), PACKS[1:2])

    assert counts["updated"] == 1
    ((id_, data),) = communities.updated
    assert id_ == "id-joss"
    assert data["metadata"]["type"] == {"id": "journal"}
    # What an admin edited stays.
    assert data["metadata"]["title"] == "JOSS, as an admin named it"
    assert data["custom_fields"] == {"rs:issn": "2475-9066"}

    # Once it has them, it isn't updated again.
    assert starter_packs.type_changes(PACKS[1], {**before, **data}) == {}


def test_the_packs_are_found_by_the_slugs_they_are_defined_with():
    communities = Service(existing={"joss", "mhh"})
    packs = [{"slug": "joss"}, {"slug": "mhh"}, {"slug": "not-yet"}]

    assert starter_packs.pack_ids(communities, packs) == {
        "joss": "id-joss",
        "mhh": "id-mhh",
    }


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
    pack = {"slug": "joss", "title": "JOSS", "type": "journal", "logo": "joss.png"}

    counts = starter_packs.create_packs(communities, Service(), [pack], tmp_path)

    assert counts["logos"] == 1
    assert communities.logos == {"id-joss": (b"PNG", 3)}

    # An admin's logo stays.
    communities.logos["id-joss"] = (b"ADMIN", 5)
    communities.existing.add("joss")
    counts = starter_packs.create_packs(communities, Service(), [pack], tmp_path)

    assert counts["logos"] == 0
    assert communities.logos == {"id-joss": (b"ADMIN", 5)}


def test_the_pidbox_jobs_offer_the_starter_packs():
    """invenio-pidbox's jobs take communities of the packs' types."""
    from invenio_rdm_starter import config

    assert config.PIDBOX_JOBS_COMMUNITY_TYPES == list(starter_packs.PACK_TYPES)


def test_a_record_needs_a_community_to_be_published():
    """The deposit form asks for one, and a record keeps its last one."""
    from invenio_rdm_starter import config

    assert config.RDM_COMMUNITY_REQUIRED_TO_PUBLISH is True
