"""The Content facet: the records with a PDF among their files."""

from __future__ import annotations

from invenio_rdm_starter import config


def test_the_content_facet_offers_pdf_only():
    facet = config.RDM_FACETS["content"]["facet"]

    assert facet.get_aggregation().to_dict() == {
        "terms": {"field": "files.types", "include": ["pdf"]}
    }
    assert facet.add_filter(["pdf"]).to_dict() == {"terms": {"files.types": ["pdf"]}}
    assert config.RDM_FACETS["content"]["ui"] == {"field": "files.types"}


def test_record_and_community_searches_offer_it():
    assert "content" in config.RDM_SEARCH["facets"]
    assert "content" in config.COMMUNITIES_RECORDS_SEARCH["facets"]
