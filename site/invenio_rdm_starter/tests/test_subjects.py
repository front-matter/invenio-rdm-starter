"""Tests for the header of a search for one OpenAlex subject."""

from importlib.metadata import entry_points
from pathlib import Path

import pytest
from invenio_rdm_starter import subjects

TEMPLATE = (
    Path(__file__).parents[3]
    / "templates/semantic-ui/invenio_app_rdm/records/search.html"
)


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            'metadata.subjects.id:"https://openalex.org/subfields/3103"',
            "https://openalex.org/subfields/3103",
        ),
        (
            'metadata.subjects.id:"https://openalex.org/T10039"',
            "https://openalex.org/T10039",
        ),
        (
            "metadata.subjects.id:https://openalex.org/fields/31",
            "https://openalex.org/fields/31",
        ),
        (
            ' metadata.subjects.id:"https://openalex.org/domains/2" ',
            "https://openalex.org/domains/2",
        ),
        # Anything else is another search, without a header.
        ('metadata.subjects.id:"https://openalex.org/subfields/3103" AND x', None),
        ('metadata.subjects.id:"http://example.org/3103"', None),
        ("astronomy", None),
        ("", None),
        (None, None),
    ],
)
def test_a_search_for_one_openalex_subject_is_recognized(query, expected):
    assert subjects.subject_id(query) == expected


def test_the_subject_is_named_from_the_vocabulary():
    entries = {
        "https://openalex.org/subfields/3103": {
            "subject": "Astronomy and Astrophysics",
            "scheme": "Subfields",
        }
    }

    subject = subjects.openalex_subject(
        'metadata.subjects.id:"https://openalex.org/subfields/3103"',
        read=entries.get,
    )

    assert subject["id"] == "https://openalex.org/subfields/3103"
    assert subject["name"] == "Astronomy and Astrophysics"
    assert str(subject["kind"]) == "Subfield"


def test_a_topic_is_a_topic_and_a_subject_not_found_has_no_name():
    def unreadable(id_):
        raise LookupError(id_)

    subject = subjects.openalex_subject(
        'metadata.subjects.id:"https://openalex.org/T10039"', read=unreadable
    )

    assert subject["name"] is None
    assert str(subject["kind"]) == "Topic"


def test_another_search_has_no_subject():
    assert subjects.openalex_subject("astronomy", read=lambda id_: {}) is None


def test_the_template_global_is_registered_and_used():
    hooks = {
        ep.name: ep.value for ep in entry_points(group="invenio_base.finalize_app")
    }
    template = TEMPLATE.read_text()

    assert (
        hooks["invenio_rdm_starter_subjects"]
        == "invenio_rdm_starter.subjects:finalize_app"
    )
    assert 'starter_openalex_subject(request.args.get("q"))' in template
    assert "page-subheader-outer" in template
    assert "InvenioAppRdm.Search" in template
