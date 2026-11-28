"""The custom fields of the Starter's communities, in the ``rs`` namespace.

A Starter Pack (:mod:`invenio_rdm_starter.starter_packs`) says which works it
holds: by the ISSN of their journal (``rs:issn``), the DOI of their blog or
journal (``rs:doi``), the prefix of their DOIs (``rs:prefix``), their
language (``rs:language``), and the license they come with (``rs:license``).
The organizations its works come from are the community's own organizations
(``metadata.organizations``), not a field of these.
The names and meanings are Rogue Scholar's community fields, so that a
community moves between the two with its fields.
"""

from __future__ import annotations

from invenio_i18n import lazy_gettext as _
from invenio_records_resources.services.custom_fields import TextCF
from invenio_vocabularies.services.custom_fields import VocabularyCF

#: The namespace of the Starter's community fields, as on Rogue Scholar.
RS_NAMESPACE = {"rs": None}


class CommunityVocabularyCF(VocabularyCF):
    """A vocabulary field whose mapping takes a community's dereferenced entry.

    A community is indexed with its vocabulary fields dereferenced, so that a
    license arrives with its ``props`` (URL, scheme) and ``icon``, which the
    mapping of a record's vocabulary field doesn't have, and indexing fails.
    As Rogue Scholar's.
    """

    @property
    def mapping(self):
        """Return the mapping, with the entry's props and icon."""
        mapping = super().mapping
        mapping["properties"].update(
            {
                "props": {"type": "object", "dynamic": "true"},
                "icon": {"type": "keyword"},
            }
        )
        return mapping


STARTER_PACK_CUSTOM_FIELDS = [
    TextCF(name="rs:issn"),
    TextCF(name="rs:doi"),
    TextCF(name="rs:prefix"),
    CommunityVocabularyCF(
        name="rs:language",
        vocabulary_id="languages",
        dump_options=False,
        multiple=False,
    ),
    CommunityVocabularyCF(
        name="rs:license",
        vocabulary_id="licenses",
        dump_options=False,
        multiple=False,
    ),
]
"""The fields of a Starter Pack: what selects its works."""


STARTER_PACK_CUSTOM_FIELDS_UI = {
    "section": _("Starter Pack"),
    "fields": [
        {
            "field": "rs:issn",
            "ui_widget": "Input",
            "props": {
                "label": "ISSN",
                "icon": "book",
                "description": _("The ISSN of the journal whose works the pack holds."),
                "placeholder": "2475-9066",
            },
        },
        {
            "field": "rs:doi",
            "ui_widget": "Input",
            "props": {
                "label": "DOI",
                "icon": "barcode",
                "description": _(
                    "The DOI of the blog or journal whose works the pack holds."
                ),
                "placeholder": "10.59350/rzepa",
            },
        },
        {
            "field": "rs:prefix",
            "ui_widget": "Input",
            "props": {
                "label": _("DOI Prefix"),
                "icon": "barcode",
                "description": _("The DOI prefix of the works the pack holds."),
                "placeholder": "10.21105",
            },
        },
        {
            "field": "rs:language",
            "ui_widget": "AutocompleteDropdown",
            "isGenericVocabulary": True,
            "props": {
                "label": _("Language"),
                "icon": "language",
                "description": _("The language of the works the pack holds."),
                "placeholder": _("Search for a language by name e.g. English ..."),
                "autocompleteFrom": "/api/vocabularies/languages",
                "autocompleteFromAcceptHeader": "application/vnd.inveniordm.v1+json",
                "required": False,
                "multiple": False,
                "clearable": True,
            },
        },
        {
            "field": "rs:license",
            "ui_widget": "AutocompleteDropdown",
            "isGenericVocabulary": True,
            "props": {
                "label": _("License"),
                "icon": "creative commons",
                "description": _("The license of the works the pack holds."),
                "placeholder": _("Search for a license by name e.g. CC-BY ..."),
                "autocompleteFrom": "/api/vocabularies/licenses",
                "autocompleteFromAcceptHeader": "application/vnd.inveniordm.v1+json",
                "required": False,
                "multiple": False,
                "clearable": True,
            },
        },
    ],
}
"""The Starter Pack section of a community's settings. A Starter Pack's
community is created by the system, so its settings are for admins."""
