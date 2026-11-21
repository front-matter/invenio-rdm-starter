"""Starter Packs, each an InvenioRDM community of type ``starterpack``.

A Starter Pack is the content an InvenioRDM Starter instance can start with:
Rogue Scholar's German-language posts, and the Journal of Open Source
Software (the content of demo.front-matter.de). The packs are defined in ``app_data/starter_packs.yaml`` (or
the file ``STARTER_PACKS_FILE`` names); the community of each pack is where
it lives in InvenioRDM, found again by its slug. Its ``rs:`` custom fields
(:mod:`invenio_rdm_starter.custom_fields`) say which works it holds.

:func:`create_starter_pack_communities` creates the community of every pack
that doesn't have one, as :mod:`invenio_rdm_starter.subject_communities` does
for the OpenAlex subfields, and features each, for the front page's carousel
of featured communities: the Starter Packs, all of them. The community type comes with the vocabulary
fixtures of a new instance; an instance set up before it gets it from the job,
since the fixtures don't add to a vocabulary that is loaded already.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
import yaml
from celery import shared_task
from flask import current_app
from invenio_access.permissions import system_identity
from invenio_pidstore.errors import PIDDoesNotExistError

#: The community type of the Starter Packs, in the communitytypes vocabulary.
COMMUNITY_TYPE = "starterpack"

#: Its title, as app_data/vocabularies/community_types.yaml has it.
COMMUNITY_TYPE_TITLE = {
    "en": "Starter Pack",
    "sv": "Startpaket",
    "de": "Starterpaket",
    "fr": "Pack de démarrage",
    "es": "Paquete de inicio",
}

#: Who can see and add to a Starter Pack: anyone sees it, its curators add
#: works to it.
COMMUNITY_ACCESS = {
    "visibility": "public",
    "members_visibility": "public",
    "member_policy": "closed",
    "record_submission_policy": "closed",
    "review_policy": "closed",
}

log = structlog.get_logger().bind(service="starter_packs")


class StarterPackError(ValueError):
    """A Starter Pack's definition is incomplete."""


def packs_file() -> Path:
    """The file the Starter Packs are defined in."""
    configured = current_app.config.get("STARTER_PACKS_FILE")
    if configured:
        return Path(configured)
    return Path(current_app.instance_path) / "app_data" / "starter_packs.yaml"


def load_packs(path: Path) -> list[dict[str, Any]]:
    """The Starter Packs defined in ``path``: each with slug and title."""
    packs = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(packs, list):
        raise StarterPackError(f"{path}: a list of Starter Packs is expected")
    for pack in packs:
        if not isinstance(pack, dict) or not pack.get("slug") or not pack.get("title"):
            raise StarterPackError(f"{path}: a Starter Pack needs a slug and a title")
    return packs


def community_data(pack: dict[str, Any]) -> dict[str, Any]:
    """The data of a Starter Pack's community."""
    metadata: dict[str, Any] = {
        "title": pack["title"],
        "type": {"id": COMMUNITY_TYPE},
    }
    if pack.get("description"):
        metadata["description"] = str(pack["description"]).strip()
    if pack.get("website"):
        metadata["website"] = pack["website"]
    data: dict[str, Any] = {
        "slug": pack["slug"],
        "access": dict(COMMUNITY_ACCESS),
        "metadata": metadata,
    }
    fields = custom_fields(pack)
    if fields:
        data["custom_fields"] = fields
    return data


#: The rs: fields whose value is a vocabulary entry, given by its id.
VOCABULARY_FIELDS = ("rs:language", "rs:license")


def custom_fields(pack: dict[str, Any]) -> dict[str, Any]:
    """A pack's rs: custom fields, as a community holds them.

    The definitions give a vocabulary field by its id (``deu``), which the
    community holds as ``{"id": "deu"}``; text fields stay as they are.
    """
    fields = {}
    for name, value in (pack.get("custom_fields") or {}).items():
        if value in (None, ""):
            continue
        if name in VOCABULARY_FIELDS and not isinstance(value, dict):
            value = {"id": str(value)}
        elif not isinstance(value, dict):
            value = str(value)
        fields[name] = value
    return fields


def ensure_community_type(vocabularies: Any) -> bool:
    """Add the ``starterpack`` community type, unless the vocabulary has it.

    Returns whether it was added.
    """
    try:
        vocabularies.read(system_identity, ("communitytypes", COMMUNITY_TYPE))
        return False
    except PIDDoesNotExistError:
        pass
    vocabularies.create(
        system_identity,
        {"id": COMMUNITY_TYPE, "title": COMMUNITY_TYPE_TITLE, "type": "communitytypes"},
    )
    log.info("community_type_created", id=COMMUNITY_TYPE)
    return True


def _read(communities: Any, slug: str) -> Any | None:
    """A pack's community, or ``None`` while it has none."""
    try:
        return communities.read(system_identity, slug)
    except PIDDoesNotExistError:
        return None


def feature(communities: Any, community_id: str) -> bool:
    """Feature a community from now, unless it is featured. Returns whether."""
    if communities.featured_list(system_identity, community_id).total:
        return False
    communities.featured_create(
        system_identity,
        community_id,
        {"start_date": datetime.now(UTC).isoformat()},
    )
    return True


def set_logo(communities: Any, community_id: str, path: Path) -> bool:
    """Give a community the logo in ``path``, unless it has one.

    A logo an admin uploads in the community's settings stays. Returns whether
    the logo was set.
    """
    from invenio_communities.errors import LogoNotFoundError

    try:
        communities.read_logo(system_identity, community_id)
        return False
    except LogoNotFoundError:
        pass
    with path.open("rb") as stream:
        communities.update_logo(
            system_identity,
            community_id,
            stream,
            content_length=path.stat().st_size,
        )
    return True


def create_packs(
    communities: Any,
    vocabularies: Any,
    packs: list[dict[str, Any]],
    base: Path | None = None,
) -> dict[str, int]:
    """Create the community of every pack that has none, and feature them all.

    The front page's carousel shows the featured communities: every Starter
    Pack, and only those. A pack's ``logo``, a path relative to ``base`` (the
    folder of the definitions), becomes its community's logo while it has none.
    """
    counts = {
        "packs": len(packs),
        "existing": 0,
        "created": 0,
        "featured": 0,
        "logos": 0,
        "failed": 0,
    }
    counts["type_created"] = int(ensure_community_type(vocabularies))
    for pack in packs:
        community = _read(communities, pack["slug"])
        try:
            if community is None:
                community = communities.create(system_identity, community_data(pack))
                counts["created"] += 1
                log.info("starter_pack_created", slug=pack["slug"], title=pack["title"])
            else:
                counts["existing"] += 1
            if feature(communities, community.id):
                counts["featured"] += 1
                log.info("starter_pack_featured", slug=pack["slug"])
            if pack.get("logo") and set_logo(
                communities, community.id, (base or Path()) / pack["logo"]
            ):
                counts["logos"] += 1
                log.info("starter_pack_logo_set", slug=pack["slug"])
        except Exception:
            # One pack failing must not stop the others; it is tried again on
            # the next run.
            counts["failed"] += 1
            log.exception("starter_pack_not_created", slug=pack["slug"])
    return counts


@shared_task(ignore_result=True)
def create_starter_pack_communities() -> dict[str, int]:
    """Create the community of every Starter Pack that has none.

    Returns ``{"packs", "existing", "created", "featured", "logos", "failed",
    "type_created"}``.
    """
    from invenio_communities.proxies import current_communities
    from invenio_vocabularies.proxies import current_service as vocabularies

    path = packs_file()
    counts = create_packs(
        current_communities.service, vocabularies, load_packs(path), path.parent
    )
    log.info("starter_pack_communities_created", **counts)
    return counts


#: The communities of the Starter Packs, by their type.
PACKS_QUERY = f"metadata.type.id:{COMMUNITY_TYPE}"


def pack_ids(communities: Any) -> dict[str, str]:
    """The Starter Packs' communities, as slug → community id."""
    result = communities.search(system_identity, params={"q": PACKS_QUERY, "size": 100})
    return {hit["slug"]: hit["id"] for hit in result.hits}


def selection_query(packs: dict[str, str], source: str | None) -> str:
    """The records in ``source``'s community, or, without one, in no pack's."""
    if source:
        return f'parent.communities.ids:"{packs[source]}"'
    if not packs:
        return "*"
    ids = " OR ".join(f'"{community_id}"' for community_id in packs.values())
    return f"NOT parent.communities.ids:({ids})"


class MoveError(ValueError):
    """A move the job can't make: no source or target, or the same one."""


def check_move(packs: dict[str, str], source: str | None, target: str | None) -> None:
    """Refuse a move from a pack to itself, or from or to a pack that isn't."""
    if (source or "") == (target or ""):
        raise MoveError("the source and the target are the same")
    for slug in (source, target):
        if slug and slug not in packs:
            raise MoveError(f"{slug} is not a Starter Pack")


def move_records(
    records: Any,
    record_communities: Any,
    packs: dict[str, str],
    source: str | None = None,
    target: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Move records from one Starter Pack's community to another's.

    The records are those in ``source``'s community, or, without a source,
    those in no Starter Pack's. Each joins ``target``'s community, then leaves
    ``source``'s, so that it is never in neither; without a target it just
    leaves ``source``'s. Communities that aren't Starter Packs are left as
    they are. ``dry_run`` only counts the records.
    """
    source, target = source or None, target or None
    check_move(packs, source, target)
    counts: dict[str, Any] = {
        "source": source or "",
        "target": target or "",
        "dry_run": dry_run,
        "records": 0,
        "moved": 0,
        "failed": 0,
    }
    query = selection_query(packs, source)
    for hit in records.scan(system_identity, params={"q": query}).hits:
        counts["records"] += 1
        if dry_run:
            continue
        current = ((hit.get("parent") or {}).get("communities") or {}).get("ids") or []
        try:
            if target and packs[target] not in current:
                _done, errors = record_communities.add(
                    system_identity, hit["id"], {"communities": [{"id": packs[target]}]}
                )
                if errors:
                    raise MoveError(f"not added to {target}: {errors}")
            if source:
                _done, errors = record_communities.remove(
                    system_identity, hit["id"], {"communities": [{"id": packs[source]}]}
                )
                if errors:
                    raise MoveError(f"not removed from {source}: {errors}")
        except Exception:
            # One record failing must not stop the others; a rerun takes it
            # again, as it is still where it was.
            counts["failed"] += 1
            log.exception("record_not_moved", record_id=hit["id"])
            continue
        counts["moved"] += 1
    log.info("records_moved_to_starter_pack", **counts)
    return counts


@shared_task(ignore_result=False)
def move_records_to_starter_pack(
    source_slug: str | None = None,
    target_slug: str | None = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Move records from one Starter Pack's community to another's.

    See :func:`move_records`; ``source_slug`` and ``target_slug`` are the
    packs' slugs, either empty for no pack.
    """
    from invenio_communities.proxies import current_communities
    from invenio_rdm_records.proxies import current_rdm_records

    return move_records(
        current_rdm_records.records_service,
        current_rdm_records.record_communities_service,
        pack_ids(current_communities.service),
        source_slug,
        target_slug,
        dry_run,
    )
