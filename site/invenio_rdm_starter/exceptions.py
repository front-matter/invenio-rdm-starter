"""InvenioRDM Starter exceptions."""


class ConfigNotLoadedError(RuntimeError):
    """The app was created without the Starter's settings.

    The settings are in :mod:`invenio_rdm_starter.config`, loaded through the
    ``invenio_config.module`` entry point ``invenio_rdm_starter``. Without it
    the app would run on InvenioRDM's defaults.
    """


class RecordDeletionRefusedError(RuntimeError):
    """Deleting all records isn't allowed here.

    Raised by :func:`invenio_rdm_starter.reset.delete_all_records` unless
    ``STARTER_DELETE_ALL_RECORDS_ENABLED`` is set, and when a DOI was minted
    here, so that the job's run fails with the reason.
    """
