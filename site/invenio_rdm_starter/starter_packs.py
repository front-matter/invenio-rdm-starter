"""Starter Packs: collections of works, each an InvenioRDM community.

A Starter Pack is the content an InvenioRDM Starter instance can start with,
a collection of works defined by one PID, such as the Journal of Open Source
Software (by its ISSN; the content of demo.front-matter.de) or the works of a
university (by its ROR id). The packs are defined in
``app_data/starter_packs.yaml`` (or the file ``STARTER_PACKS_FILE`` names);
the community of each pack is where it lives in InvenioRDM, found again by its
slug. Its community type says what kind of collection it is
(:data:`PACK_TYPES`: a journal, blog or repository, an organization or a
funder), and its ``rs:`` custom fields (:mod:`invenio_rdm_starter.
custom_fields`) which works it holds. Nothing else marks a community as a
pack: the packs are those the definitions name.

:func:`create_starter_pack_communities` (the "Sync starter packs" job) creates
the community of every pack that doesn't have one, as
:mod:`invenio_rdm_starter.subject_communities` does for the OpenAlex
subfields, gives an existing one the pack's type, and features
each, for the front page's carousel of featured communities: the Starter
Packs, all of them. The community types, and the resource types (Award, for a
funder's pack), come with the vocabulary fixtures of a new instance; an
instance set up before one of them gets it from the job, since the fixtures
don't add to a vocabulary that is loaded already. An entry it has already
gets the tags of the file it lacks: Award needs ``depositable``, which
InvenioRDM checks a record's resource type for, to be one at all.
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

#: The community types a Starter Pack can have, in the communitytypes
#: vocabulary: what kind of collection of works it is. invenio-pidbox's jobs
#: take the communities of these types (PIDBOX_JOBS_COMMUNITY_TYPES).
PACK_TYPES = ("journal", "blog", "repository", "organization", "funder")

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


#: The vocabularies the job adds missing entries to, from the files of
#: app_data/vocabularies they are loaded from: the community types (a pack's
#: type) and the resource types (Award, for a funder's pack).
VOCABULARY_FILES = {
    "communitytypes": "community_types.yaml",
    "resourcetypes": "resource_types.yaml",
}


def vocabulary_file(vocabulary_type: str) -> Path:
    """The file a vocabulary of :data:`VOCABULARY_FILES` is loaded from."""
    return (
        Path(current_app.instance_path)
        / "app_data"
        / "vocabularies"
        / VOCABULARY_FILES[vocabulary_type]
    )


def load_vocabulary_entries(vocabulary_type: str) -> list[dict[str, Any]]:
    """The entries of a vocabulary's file, or none without the file."""
    path = vocabulary_file(vocabulary_type)
    if not path.exists():
        return []
    return yaml.safe_load(path.read_text(encoding="utf-8")) or []


def load_packs(path: Path) -> list[dict[str, Any]]:
    """The Starter Packs defined in ``path``.

    Each has a slug, a title and a type of :data:`PACK_TYPES`.
    """
    packs = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(packs, list):
        raise StarterPackError(f"{path}: a list of Starter Packs is expected")
    for pack in packs:
        if not isinstance(pack, dict) or not pack.get("slug") or not pack.get("title"):
            raise StarterPackError(f"{path}: a Starter Pack needs a slug and a title")
        if pack.get("type") not in PACK_TYPES:
            raise StarterPackError(
                f"{path}: {pack['slug']}'s type is one of {', '.join(PACK_TYPES)}"
            )
    return packs


def community_data(pack: dict[str, Any]) -> dict[str, Any]:
    """The data of a Starter Pack's community."""
    metadata: dict[str, Any] = {
        "title": pack["title"],
        "type": {"id": pack["type"]},
    }
    if pack.get("description"):
        metadata["description"] = str(pack["description"]).strip()
    if pack.get("website"):
        metadata["website"] = pack["website"]
    organizations = [
        {"id": _bare_ror(ror)} for ror in pack.get("organizations") or [] if ror
    ]
    if organizations:
        metadata["organizations"] = organizations
    data: dict[str, Any] = {
        "slug": pack["slug"],
        "access": dict(COMMUNITY_ACCESS),
        "metadata": metadata,
    }
    fields = custom_fields(pack)
    if fields:
        data["custom_fields"] = fields
    return data


def type_changes(pack: dict[str, Any], community: dict[str, Any]) -> dict[str, Any]:
    """What a pack's existing community needs to take the pack's type, or nothing.

    Returns the community's data with the pack's type, to update it with, or
    an empty dict when it has it already. The rest of the community, which
    admins edit in its settings, is left as it is.
    """
    metadata = community.get("metadata") or {}
    if (metadata.get("type") or {}).get("id") == pack["type"]:
        return {}
    return {
        "slug": community["slug"],
        "access": community.get("access") or {},
        "metadata": {**metadata, "type": {"id": pack["type"]}},
        "custom_fields": community.get("custom_fields") or {},
    }


def _bare_ror(value: str) -> str:
    """A ROR id without its URL: the id of the community's organization."""
    return str(value).strip().removeprefix("https://ror.org/")


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


#: The fields of a vocabulary entry the job writes.
VOCABULARY_ENTRY_FIELDS = ("id", "title", "description", "props", "icon", "tags")


def ensure_vocabulary_entries(
    vocabularies: Any, vocabulary_type: str, entries: list[dict[str, Any]]
) -> tuple[int, int]:
    """Add the entries of a vocabulary the instance doesn't have yet.

    ``entries`` are those of the vocabulary's file in app_data/vocabularies.
    An entry the instance has keeps what it has, and gets the tags of the file
    it lacks: a tag decides what an entry is for, as ``depositable`` decides
    whether a record can have a resource type. Returns how many entries were
    added, and how many given tags.
    """
    added = updated = 0
    for entry in entries:
        try:
            existing = vocabularies.read(
                system_identity, (vocabulary_type, entry["id"])
            ).to_dict()
        except PIDDoesNotExistError:
            existing = None
        if existing is None:
            data = {key: entry[key] for key in VOCABULARY_ENTRY_FIELDS if key in entry}
            vocabularies.create(system_identity, {**data, "type": vocabulary_type})
            added += 1
            log.info("vocabulary_entry_created", type=vocabulary_type, id=entry["id"])
            continue
        tags = list(existing.get("tags") or [])
        missing = [tag for tag in entry.get("tags") or [] if tag not in tags]
        if not missing:
            continue
        data = {
            key: existing[key] for key in VOCABULARY_ENTRY_FIELDS if key in existing
        }
        vocabularies.update(
            system_identity,
            (vocabulary_type, entry["id"]),
            {**data, "tags": tags + missing, "type": vocabulary_type},
        )
        updated += 1
        log.info(
            "vocabulary_entry_tagged",
            type=vocabulary_type,
            id=entry["id"],
            tags=missing,
        )
    return added, updated


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
    vocabulary_entries: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, int]:
    """Create or update the community of every pack, and feature them all.

    A pack without a community gets one; an existing one takes the pack's type.
    The front page's carousel shows the featured communities:
    every Starter Pack, and only those. A pack's ``logo``, a path relative to
    ``base`` (the folder of the definitions), becomes its community's logo
    while it has none. ``vocabulary_entries`` (by vocabulary type, the entries
    of its file) are added where the instance's vocabulary lacks them, and
    given the tags of the file where it has them without.
    """
    counts = {
        "packs": len(packs),
        "existing": 0,
        "created": 0,
        "updated": 0,
        "featured": 0,
        "logos": 0,
        "failed": 0,
    }
    counts["vocabulary_entries_created"] = 0
    counts["vocabulary_entries_updated"] = 0
    for vocabulary_type, entries in (vocabulary_entries or {}).items():
        added, updated = ensure_vocabulary_entries(
            vocabularies, vocabulary_type, entries
        )
        counts["vocabulary_entries_created"] += added
        counts["vocabulary_entries_updated"] += updated
    for pack in packs:
        community = _read(communities, pack["slug"])
        try:
            if community is None:
                community = communities.create(system_identity, community_data(pack))
                counts["created"] += 1
                log.info("starter_pack_created", slug=pack["slug"], title=pack["title"])
            else:
                counts["existing"] += 1
                changes = type_changes(pack, community.to_dict())
                if changes:
                    community = communities.update(
                        system_identity, community.id, changes
                    )
                    counts["updated"] += 1
                    log.info(
                        "starter_pack_updated", slug=pack["slug"], type=pack["type"]
                    )
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
    """Create or update the community of every Starter Pack.

    Returns ``{"packs", "existing", "created", "updated", "featured", "logos",
    "failed", "vocabulary_entries_created", "vocabulary_entries_updated"}``.
    """
    from invenio_communities.proxies import current_communities
    from invenio_vocabularies.proxies import current_service as vocabularies

    path = packs_file()
    counts = create_packs(
        current_communities.service,
        vocabularies,
        load_packs(path),
        path.parent,
        vocabulary_entries={
            vocabulary_type: load_vocabulary_entries(vocabulary_type)
            for vocabulary_type in VOCABULARY_FILES
        },
    )
    log.info("starter_pack_communities_created", **counts)
    return counts


def pack_ids(
    communities: Any, packs: list[dict[str, Any]] | None = None
) -> dict[str, str]:
    """The Starter Packs' communities, as slug → community id.

    The packs are those the definitions name (``packs``, or the packs file);
    a pack without a community yet is left out.
    """
    if packs is None:
        packs = load_packs(packs_file())
    ids = {}
    for pack in packs:
        community = _read(communities, pack["slug"])
        if community is not None:
            ids[pack["slug"]] = str(community.id)
    return ids


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


#: Records added to the target in one bulk add.
MOVE_BATCH_SIZE = 100


def _added(
    record_communities: Any, community_id: str, record_ids: list[str]
) -> set[str]:
    """Add records to a community in bulk, and return those now in it.

    A bulk add includes records without a request, so without the request's
    notification, which can't name its creator, the system, as a user. A
    record already in the community is in it.
    """
    errors = record_communities.bulk_add(system_identity, community_id, record_ids)
    refused = set()
    for error in errors or []:
        if "already included" in str(error.get("message", "")).lower():
            continue
        refused.add(error.get("record_id"))
        log.warning("record_not_added", record_id=error.get("record_id"), error=error)
    return {record_id for record_id in record_ids if record_id not in refused}


def move_records(
    records: Any,
    record_communities: Any,
    packs: dict[str, str],
    source: str | None = None,
    target: str | None = None,
    dry_run: bool = True,
    batch_size: int = MOVE_BATCH_SIZE,
) -> dict[str, Any]:
    """Move records from one Starter Pack's community to another's.

    The records are those in ``source``'s community, or, without a source,
    those in no Starter Pack's. They join ``target``'s community, in bulk and
    without inclusion requests, and then leave ``source``'s, so that a record
    is never in neither; without a target they just leave ``source``'s.
    Communities that aren't Starter Packs are left as they are. ``dry_run``
    only counts the records.
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

    def move(batch: list[str]) -> None:
        try:
            moving = (
                _added(record_communities, packs[target], batch)
                if target
                else set(batch)
            )
        except Exception:
            # The batch failing must not stop the others; a rerun takes its
            # records again, as they are still where they were.
            counts["failed"] += len(batch)
            log.exception("records_not_added", records=len(batch))
            return
        counts["failed"] += len(batch) - len(moving)
        for record_id in batch:
            if record_id not in moving:
                continue
            if source:
                try:
                    _done, errors = record_communities.remove(
                        system_identity,
                        record_id,
                        {"communities": [{"id": packs[source]}]},
                    )
                    if errors:
                        raise MoveError(f"not removed from {source}: {errors}")
                except Exception:
                    counts["failed"] += 1
                    log.exception("record_not_moved", record_id=record_id)
                    continue
            counts["moved"] += 1

    # Read whole before any record is moved: the scan keeps its search
    # context only minutes between pages, and moving records as it reads
    # outlives it ("No search context found").
    query = selection_query(packs, source)
    record_ids = [
        hit["id"] for hit in records.scan(system_identity, params={"q": query}).hits
    ]
    counts["records"] = len(record_ids)
    if not dry_run:
        for start in range(0, len(record_ids), batch_size):
            move(record_ids[start : start + batch_size])
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
