"""InvenioRDM Starter exceptions."""


class ConfigNotLoadedError(RuntimeError):
    """The app was created without the Starter's settings.

    The settings are in :mod:`invenio_rdm_starter.config`, loaded through the
    ``invenio_config.module`` entry point ``invenio_rdm_starter``. Without it
    the app would run on InvenioRDM's defaults.
    """
