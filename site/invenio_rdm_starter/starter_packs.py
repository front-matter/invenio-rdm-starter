"""Starter Packs, each an InvenioRDM community of type ``starterpack``.

A Starter Pack is the content an InvenioRDM Starter instance can start with:
Rogue Scholar's German-language posts, the Journal of Open Source Software
(the content of demo.front-matter.de), arXiv's cs.DL preprints with COMET
enhancements. The packs are defined in ``app_data/starter_packs.yaml`` (or
the file ``STARTER_PACKS_FILE`` names); the community of each pack is where
it lives in InvenioRDM, found again by its slug.

:func:`create_starter_pack_communities` creates the community of every pack
that doesn't have one, as :mod:`invenio_rdm_starter.subject_communities` does
for the OpenAlex subfields. The community type comes with the vocabulary
fixtures of a new instance; an instance set up before it gets it from the job,
since the fixtures don't add to a vocabulary that is loaded already.
"""

from __future__ import annotations

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
    return {
        "slug": pack["slug"],
        "access": dict(COMMUNITY_ACCESS),
        "metadata": metadata,
    }


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


def _exists(communities: Any, slug: str) -> bool:
    try:
        communities.read(system_identity, slug)
        return True
    except PIDDoesNotExistError:
        return False


def create_packs(
    communities: Any, vocabularies: Any, packs: list[dict[str, Any]]
) -> dict[str, int]:
    """Create the community of every pack that doesn't have one."""
    counts = {"packs": len(packs), "existing": 0, "created": 0, "failed": 0}
    counts["type_created"] = int(ensure_community_type(vocabularies))
    for pack in packs:
        if _exists(communities, pack["slug"]):
            counts["existing"] += 1
            continue
        try:
            communities.create(system_identity, community_data(pack))
        except Exception:
            # One pack failing must not stop the others; it is tried again on
            # the next run.
            counts["failed"] += 1
            log.exception("starter_pack_not_created", slug=pack["slug"])
            continue
        counts["created"] += 1
        log.info("starter_pack_created", slug=pack["slug"], title=pack["title"])
    return counts


@shared_task(ignore_result=True)
def create_starter_pack_communities() -> dict[str, int]:
    """Create the community of every Starter Pack that has none.

    Returns ``{"packs", "existing", "created", "failed", "type_created"}``.
    """
    from invenio_communities.proxies import current_communities
    from invenio_vocabularies.proxies import current_service as vocabularies

    counts = create_packs(
        current_communities.service, vocabularies, load_packs(packs_file())
    )
    log.info("starter_pack_communities_created", **counts)
    return counts
