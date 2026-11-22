"""The OpenAlex subject a search is for, for a header above its results.

A record's subjects link to a search for the records with that subject, as
``metadata.subjects.id:"https://openalex.org/subfields/3103"`` (an OpenAlex
domain, field, subfield or topic, in the subjects vocabulary the Starter
loads from app_data/vocabularies/subjects_openalex_*.yaml). The record search
(templates/semantic-ui/invenio_app_rdm/records/search.html) shows such a
search under a header with the subject's name, kind and OpenAlex ID, as a
community's pages show the community.

:func:`openalex_subject` is the template global ``starter_openalex_subject``,
through the ``invenio_base.finalize_app`` entry point
``invenio_rdm_starter_subjects``.
"""

from __future__ import annotations

import re
from typing import Any

import structlog
from flask import Flask
from invenio_i18n import lazy_gettext as _

#: A query that is only one OpenAlex subject: a domain, field or subfield by
#: its number, or a topic by its T ID.
SUBJECT_QUERY = re.compile(
    r'^\s*metadata\.subjects\.id:"?'
    r"(https://openalex\.org/(?:(?:domains|fields|subfields)/\d+|T\d+))"
    r'"?\s*$'
)

#: The kind of subject, by the part of the ID that says it.
KINDS = {
    "domains": _("Domain"),
    "fields": _("Field"),
    "subfields": _("Subfield"),
    "topics": _("Topic"),
}

log = structlog.get_logger().bind(service="subjects")


def subject_id(query: str | None) -> str | None:
    """The OpenAlex subject ID a query is for, or ``None``."""
    match = SUBJECT_QUERY.match(query or "")
    return match.group(1) if match else None


def kind_of(subject: str) -> str:
    """The kind of an OpenAlex subject ID: domains, fields, subfields, topics."""
    path = subject.removeprefix("https://openalex.org/")
    return path.split("/", 1)[0] if "/" in path else "topics"


def openalex_subject(query: str | None, read: Any = None) -> dict[str, Any] | None:
    """The OpenAlex subject a search is for, or ``None`` for another search.

    Returns ``{"id", "name", "kind"}``: the subject's name from the subjects
    vocabulary, or no name when it isn't there; ``kind`` the translated label.
    ``read(id)`` returns the vocabulary's entry (for tests).
    """
    id_ = subject_id(query)
    if id_ is None:
        return None
    name = None
    try:
        entry = (read or _read_subject)(id_)
        name = (entry or {}).get("subject")
    except Exception as error:  # noqa: BLE001 - no name: the header shows the ID
        log.warning("subject_not_read", id=id_, error=str(error))
    return {"id": id_, "name": name, "kind": KINDS[kind_of(id_)]}


def _read_subject(id_: str) -> dict[str, Any]:
    """The subjects vocabulary's entry for ``id_``."""
    from invenio_access.permissions import system_identity
    from invenio_records_resources.proxies import current_service_registry

    return current_service_registry.get("subjects").read(system_identity, id_).to_dict()


def finalize_app(app: Flask) -> None:
    """Make ``starter_openalex_subject`` a template global."""
    app.add_template_global(openalex_subject, "starter_openalex_subject")
