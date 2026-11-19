"""Jobs the Starter offers in Administration → Jobs."""

from __future__ import annotations

from invenio_i18n import lazy_gettext as _
from invenio_jobs.jobs import JobType

from .subject_communities import sync_subject_communities


class SubjectCommunitiesJob(JobType):
    """Create the OpenAlex subfield communities and fill them."""

    id = "starter_subject_communities"
    title = _("Subject communities")
    description = _(
        "Create a community for every OpenAlex subfield the records name, and "
        "add each record to the communities of its subfields."
    )

    task = sync_subject_communities

    @classmethod
    def build_task_arguments(cls, job_obj, since=None, **kwargs):
        """Return no arguments, deliberately ignoring ``since``.

        A record gains a subfield when it is enriched, which happens to the
        record's metadata but may predate the last run's start, and a record
        already in its communities costs only a comparison. So each run goes
        over every record with a subfield.

        The dashboard's custom arguments still take precedence:
        ``{"max_records": 100}`` bounds a first run.
        """
        return {}
