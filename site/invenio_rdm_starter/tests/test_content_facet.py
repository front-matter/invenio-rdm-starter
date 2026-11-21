"""The Content facet: the records with a PDF among their files."""

from __future__ import annotations

from invenio_rdm_starter import config


def test_the_content_facet_offers_pdf_and_zip():
    facet = config.RDM_FACETS["content"]["facet"]

    assert facet.get_aggregation().to_dict() == {
        "terms": {"field": "files.types", "include": ["pdf", "zip"]}
    }
    assert facet.add_filter(["zip"]).to_dict() == {"terms": {"files.types": ["zip"]}}
    assert facet._value_labels == {"pdf": "PDF", "zip": "ZIP"}
    assert config.RDM_FACETS["content"]["ui"] == {"field": "files.types"}


def test_record_and_community_searches_offer_it_last():
    assert config.RDM_SEARCH["facets"][-1] == "content"
    assert config.COMMUNITIES_RECORDS_SEARCH["facets"][-1] == "content"
