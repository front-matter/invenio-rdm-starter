"""The identifier schemes the Starter adds to InvenioRDM's."""

from __future__ import annotations

import pytest
from invenio_rdm_starter import config


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("https://openalex.org/W7171557944", True),
        ("W7171557944", True),
        ("https://openalex.org/A5023888391", False),
        ("http://openalex.org/W7171557944", False),
        ("https://openalex.org/W7171557944x", False),
        ("", False),
    ],
)
def test_an_openalex_id_is_a_work_id(value, valid):
    assert config.is_openalex_work(value) is valid


def test_openalex_is_a_scheme_before_other():
    schemes = list(config.RDM_RECORDS_IDENTIFIERS_SCHEMES)

    assert "openalex" in schemes
    assert schemes[-1] == "other"
    assert config.RDM_RECORDS_IDENTIFIERS_SCHEMES["openalex"]["datacite"] == "Other"
    # InvenioRDM's own schemes are kept.
    assert {"doi", "wikidata", "url", "uuid", "guid"} <= set(schemes)
