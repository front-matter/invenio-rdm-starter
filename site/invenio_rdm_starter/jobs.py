"""Jobs the Starter offers in Administration → Jobs."""

from __future__ import annotations

from invenio_i18n import lazy_gettext as _
from invenio_jobs.jobs import JobType, PredefinedArgsSchema
from marshmallow import ValidationError, fields, validate, validates_schema

from .reset import delete_all_records
from .starter_packs import (
    create_starter_pack_communities,
    move_records_to_starter_pack,
    pack_ids,
)


class _EverythingEachRun(JobType):
    """A job that goes over everything on each run, whatever ``since`` says."""

    @classmethod
    def build_task_arguments(cls, job_obj, since=None, **kwargs):
        """Return no arguments, deliberately ignoring ``since``.

        What is already done costs a comparison, so each run goes over
        everything. The dashboard's custom arguments still take precedence.
        """
        return {}


class CreateStarterPackCommunitiesJob(_EverythingEachRun):
    """Create or update the communities of the Starter Packs.

    The id is the job's first, so that the job registered under it before
    keeps running.
    """

    id = "starter_create_starter_pack_communities"
    title = _("Sync starter packs")
    description = _(
        "Create a community for every Starter Pack in app_data/starter_packs.yaml "
        "that doesn't have one, give an existing one the pack's type and "
        "subtype, add community and resource types the vocabularies lack, and "
        "feature the "
        "packs on the front page."
    )

    task = create_starter_pack_communities


class StarterPackSlug(validate.Validator):
    """A Starter Pack's slug, or none: the choices of a select.

    The administration form renders a field whose validator has ``choices``
    as a select of them, read when the form is: the Starter Packs' communities
    as they are, and none ("") first.
    """

    @staticmethod
    def _slugs() -> list[str]:
        try:
            from invenio_communities.proxies import current_communities

            return sorted(pack_ids(current_communities.service))
        except Exception:  # noqa: BLE001 - no app or index: no packs to offer
            return []

    @property
    def choices(self) -> list[str]:
        """None, then the Starter Packs' slugs."""
        return ["", *self._slugs()]

    def __call__(self, value):
        """Accept none, or a Starter Pack's slug."""
        if value and value not in self._slugs():
            raise ValidationError(f"{value} is not a Starter Pack.")
        return value


class MoveRecordsArgsSchema(PredefinedArgsSchema):
    """From which Starter Pack to which, and whether the run only counts."""

    class Meta:
        """``since`` doesn't apply: the records are those where they are."""

        exclude = ("since",)

    job_arg_schema = fields.String(
        metadata={"type": "hidden"},
        dump_default="MoveRecordsArgsSchema",
        load_default="MoveRecordsArgsSchema",
    )
    dry_run = fields.Boolean(
        load_default=True,
        allow_none=True,
        metadata={
            "title": "Dry run",
            "description": "Only count the records that would be moved.",
            "order": 1,
        },
    )
    source_slug = fields.String(
        load_default=None,
        allow_none=True,
        validate=StarterPackSlug(),
        metadata={
            "title": "From",
            "description": (
                "The Starter Pack whose records are moved; none for the "
                "records in no Starter Pack."
            ),
            "order": 2,
        },
    )
    target_slug = fields.String(
        load_default=None,
        allow_none=True,
        validate=StarterPackSlug(),
        metadata={
            "title": "To",
            "description": (
                "The Starter Pack the records are moved to; none to take them "
                "out of their Starter Pack."
            ),
            "order": 3,
        },
    )

    @validates_schema
    def different_packs(self, data, **kwargs):
        """From a pack to itself is no move."""
        if (data.get("source_slug") or "") == (data.get("target_slug") or ""):
            raise ValidationError("From and To are the same.", field_name="target_slug")


class MoveRecordsToStarterPackJob(JobType):
    """Move records from one Starter Pack's community to another's."""

    id = "starter_move_records_to_starter_pack"
    title = _("Move records to starter pack")
    description = _(
        "Move the records of a Starter Pack's community, or the records in no "
        "Starter Pack, to another Starter Pack's community, or out of their "
        "Starter Pack. Starts as a dry run."
    )
    task = move_records_to_starter_pack
    arguments_schema = MoveRecordsArgsSchema

    @classmethod
    def build_task_arguments(cls, job_obj, since=None, **kwargs):
        """Return ``dry_run``, on unless switched off, and the packs."""
        dry_run = kwargs.get("dry_run")
        return {
            "dry_run": True if dry_run is None else bool(dry_run),
            "source_slug": kwargs.get("source_slug") or None,
            "target_slug": kwargs.get("target_slug") or None,
        }


class DeleteAllRecordsArgsSchema(PredefinedArgsSchema):
    """Whether the run only counts."""

    class Meta:
        """``since`` doesn't apply: every record goes."""

        exclude = ("since",)

    job_arg_schema = fields.String(
        metadata={"type": "hidden"},
        dump_default="DeleteAllRecordsArgsSchema",
        load_default="DeleteAllRecordsArgsSchema",
    )
    dry_run = fields.Boolean(
        load_default=True,
        allow_none=True,
        metadata={
            "title": "Dry run",
            "description": "Only count the records, drafts, requests and PIDs.",
            "order": 1,
        },
    )


class DeleteAllRecordsJob(JobType):
    """Delete every record, to start a demo instance afresh."""

    id = "starter_delete_all_records"
    title = _("Delete all records")
    description = _(
        "Delete every record, with its drafts, versions, requests and PIDs, "
        "and empty the record indices; users, communities, vocabularies and "
        "pages stay. Only where STARTER_DELETE_ALL_RECORDS_ENABLED is set and "
        "no DOI was minted here. Starts as a dry run."
    )
    task = delete_all_records
    arguments_schema = DeleteAllRecordsArgsSchema

    @classmethod
    def build_task_arguments(cls, job_obj, since=None, **kwargs):
        """Return ``dry_run``, on unless switched off."""
        dry_run = kwargs.get("dry_run")
        return {"dry_run": True if dry_run is None else bool(dry_run)}
