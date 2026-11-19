"""Template filters of the InvenioRDM Starter."""

from __future__ import annotations

from babel_edtf import EDTFTypeError, EDTFValueError, format_edtf
from invenio_i18n import get_locale


def format_edtf_date(
    value: str | None, format: str = "long", locale: str | None = None
) -> str:
    """Return an EDTF date or interval formatted for the reader's language.

    As invenio-rdm-records formats the publication date for the record page
    ("November 12, 2025", "12. November 2025"), so that the dates section
    reads the same. EDTF that babel-edtf doesn't format, such as an
    uncertain "2025~", and anything that isn't EDTF, is shown as stored.
    """
    if not value:
        return ""
    try:
        return format_edtf(value, format=format, locale=locale or get_locale())
    except EDTFValueError, EDTFTypeError:
        return value
