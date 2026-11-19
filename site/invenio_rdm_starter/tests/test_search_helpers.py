"""Tests for the Starter's query parser helper and search facets."""

from invenio_rdm_records import config as rdm_config
from invenio_rdm_starter import config as starter_config
from invenio_rdm_starter.queryparser import word_doi
from luqum.tree import Phrase, Word


def test_a_doi_is_quoted():
    """A DOI holds slashes and dots that the query syntax would split on."""
    result = word_doi(Word("10.5281/zenodo.123"))

    assert isinstance(result, Phrase)
    assert result.value == '"10.5281/zenodo.123"'


def test_other_words_are_left_alone():
    word = Word("climate")

    assert word_doi(word) is word


def test_the_publication_date_facet_is_invenio_rdms():
    """InvenioRDM v14's date facet and its date range UI, as on Rogue Scholar."""
    assert (
        starter_config.RDM_FACETS["publication_date"]
        is rdm_config.RDM_FACETS["publication_date"]
    )
    assert starter_config.RDM_FACETS["publication_date"]["ui"]["type"] == "date"
