"""Tests for the Starter's query parser helper and publication year facet."""

from datetime import datetime

import pytest
from invenio_rdm_starter.facets import DateHistogramFacet
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


def _year_facet() -> DateHistogramFacet:
    return DateHistogramFacet(
        field="metadata.publication_date_range",
        label="Publication year",
        interval="year",
        format="yyyy",
    )


@pytest.mark.parametrize(
    ("value", "start", "end"),
    [
        pytest.param("2020", datetime(2020, 1, 1), datetime(2021, 1, 1), id="a year"),
        pytest.param(
            "2018--2020", datetime(2018, 1, 1), datetime(2021, 1, 1), id="a range"
        ),
        pytest.param(
            "2020--2018", datetime(2018, 1, 1), datetime(2021, 1, 1), id="reversed"
        ),
        pytest.param(
            "2020--2020",
            datetime(2020, 1, 1),
            datetime(2021, 1, 1),
            id="one-year range",
        ),
    ],
)
def test_a_year_filter_covers_whole_years(value, start, end):
    query = _year_facet().get_value_filter(value).to_dict()

    assert query == {
        "range": {"metadata.publication_date_range": {"gte": start, "lt": end}}
    }


def test_a_value_that_is_no_year_matches_nothing_rather_than_failing():
    query = _year_facet().get_value_filter("not-a-year").to_dict()

    assert query == {"range": {"metadata.publication_date_range": {"gte": 0, "lt": 1}}}
