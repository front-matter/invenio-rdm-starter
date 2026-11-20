"""Jobs the Starter offers in Administration → Jobs."""

from __future__ import annotations

from invenio_i18n import lazy_gettext as _
from invenio_jobs.jobs import JobType, PredefinedArgsSchema
from marshmallow import fields

from .reset import delete_all_records
from .subject_communities import (
    add_records_to_subject_communities,
    create_subject_communities,
)


class _EverythingEachRun(JobType):
    """A job that goes over everything on each run, whatever ``since`` says."""

    @classmethod
    def build_task_arguments(cls, job_obj, since=None, **kwargs):
        """Return no arguments, deliberately ignoring ``since``.

        A record gains a subfield when it is enriched, which says nothing about
        when the job last ran, and what is already done costs a comparison. The
        dashboard's custom arguments still take precedence.
        """
        return {}


class CreateSubjectCommunitiesJob(_EverythingEachRun):
    """Create the communities of the OpenAlex subfields."""

    id = "starter_create_subject_communities"
    title = _("Create subject communities")
    description = _(
        "Create a community for every OpenAlex subfield in the subjects "
        "vocabulary that doesn't have one."
    )

    task = create_subject_communities


class AddRecordsToSubjectCommunitiesJob(_EverythingEachRun):
    """Add the records to the communities of their OpenAlex subfields."""

    id = "starter_add_records_to_subject_communities"
    title = _("Add records to subject communities")
    description = _(
        "Add each record with OpenAlex subfields to the communities of its "
        'subfields. Run "Create subject communities" first; a subfield '
        "without a community is skipped."
    )

    task = add_records_to_subject_communities


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
