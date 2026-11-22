"""Tests for the citations beside a record's views and downloads."""

from pathlib import Path

ROOT = Path(__file__).parents[3]


def test_most_cited_sorts_the_record_searches():
    from invenio_rdm_starter import config

    assert config.RDM_SORT_OPTIONS["mostcited"]["fields"] == [
        "-custom_fields.pidbox:citation_count"
    ]
    assert "mostcited" in config.RDM_SEARCH["sort"]
    assert "mostcited" in config.COMMUNITIES_RECORDS_SEARCH["sort"]


def test_the_citations_facet_filters_the_cited_records():
    from invenio_rdm_starter import config

    assert config.RDM_FACETS["citations"]["ui"] == {
        "field": "custom_fields.pidbox:cited"
    }
    assert "citations" in config.RDM_SEARCH["facets"]


def test_the_count_fields_are_registered_for_the_search_index():
    from invenio_rdm_starter import config

    names = [field.name for field in config.RDM_CUSTOM_FIELDS]
    assert "pidbox:citation_count" in names
    assert "pidbox:cited" in names


def test_the_record_page_shows_this_versions_citations():
    template = (
        ROOT / "templates/semantic-ui/invenio_app_rdm/records/details/stats.html"
    ).read_text()

    assert "three statistics" in template
    assert '(record_ui.get("custom_fields") or {}).get("pidbox:citations")' in template
    assert template.count('{{ _("Citations") }}') == 2
    assert "{{ stats_popup(citations) }}" in template


def test_the_list_view_shows_the_citation_count():
    item = (
        ROOT / "assets/js/invenio_app_rdm/overridableRegistry/RecordsResultsListItem.js"
    ).read_text()
    count = (
        ROOT / "assets/js/invenio_app_rdm/overridableRegistry/citationCount.js"
    ).read_text()

    assert "<CitationCount result={result} />" in item
    assert '"pidbox:citation_count"' in count
