"""InvenioRDM settings for the InvenioRDM Starter.

Loaded through the ``invenio_config.module`` entry point
``invenio_rdm_starter`` (pyproject.toml). invenio-config loads entry points in
alphabetical order of their names, so this module comes after
invenio-app-rdm's ``invenio_app_rdm``. An invenio.cfg in the instance folder
comes after both, and the INVENIO_ environment variables after that. Keeping
the settings in the package makes them importable by tests and linted with the
rest of the code; invenio.cfg only has comments.

For the full list of settings and their values, see
https://inveniordm.docs.cern.ch/reference/.
"""

import os
from copy import deepcopy
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
import idutils
from invenio_rdm_records.services.pids import providers
from invenio_rdm_records.contrib.journal import (
    JOURNAL_CUSTOM_FIELDS,
    JOURNAL_CUSTOM_FIELDS_UI,
    JOURNAL_NAMESPACE,
)
from invenio_records_resources.services.records.queryparser import (
    FieldValueMapper,
    QueryParser,
    SearchFieldTransformer,
)
from invenio_search.engine import dsl
from invenio_records_resources.services.records.facets.facets import (
    LabelledFacetMixin,
    TermsFacet,
)
from invenio_communities.communities.records.models import CommunityMetadata
from invenio_db import db
from luqum.tree import Phrase
from invenio_access import action_factory
from invenio_records.dictutils import dict_lookup
from invenio_records_permissions.generators import (
    ConditionalGenerator,
    Generator,
)
from invenio_communities.permissions import CommunityPermissionPolicy
from invenio_rdm_records.services.generators import (
    AccessGrant,
    RecordOwners,
)
from invenio_rdm_records.services.permissions import RDMRecordPermissionPolicy
from invenio_records_permissions.generators import (
    SystemProcess,
)

# invenio-oauthclient comes from the max-moser/invenio-oauthclient mm/authlib
# branch, a rewrite on authlib, as for Rogue Scholar. See the Authentication
# section.
from invenio_oauthclient.views.views import auto_redirect_login
from invenio_rdm_starter.oidc import (
    GitHubRemoteApp,
    OAuthClientRemoteApp,
    client_credentials,
    signup_form,
)
from invenio_rdm_records.services import facets
from invenio_pidbox.facets import StoreAffiliationsLabels, StoreFundersLabels
from invenio_vocabularies.services.facets import VocabularyLabels
from invenio_s3 import s3fs_storage_factory

# Which module these settings came from. invenio_rdm_starter.views refuses to
# start without it: if the package is installed without its
# invenio_config.module entry point (e.g. a venv not synced since the entry
# point was added), the app would otherwise run on InvenioRDM's defaults
# without saying so.
INVENIO_RDM_STARTER_CONFIG_MODULE = __name__


def _(x):  # needed to avoid start time failure with lazy strings
    return x


RATELIMIT_ENABLED = True
RATELIMIT_AUTHENTICATED_USER = "60000 per hour;1100 per minute"
RATELIMIT_GUEST_USER = "30000 per hour;500 per minute"

# Flask
# =====
# See https://flask.palletsprojects.com/en/1.1.x/config/

# Define the value of the cache control header `max-age` returned by the server when serving
# public files. Files will be cached by the browser for the provided number of seconds.
# See flask documentation for more information:
# https://flask.palletsprojects.com/en/2.1.x/config/#SEND_FILE_MAX_AGE_DEFAULT
SEND_FILE_MAX_AGE_DEFAULT = 300

# Set via env variable
# SECRET_KEY=

# Since HAProxy and Nginx route all requests no matter the host header
# provided, the allowed hosts variable is set to localhost. In production it
# should be set to the correct host and it is strongly recommended to only
# route correct hosts to the application.
TRUSTED_HOSTS = ["localhost", "127.0.0.1"]


# Flask-SQLAlchemy
# ================
# See https://flask-sqlalchemy.palletsprojects.com/en/2.x/config/

# Set via env variable
# SQLALCHEMY_DATABASE_URI=

LOGGING_CONSOLE_LEVEL = "ERROR"
LOGGING_FS_LEVEL = "ERROR"


# Invenio-App
# ===========
# See https://invenio-app.readthedocs.io/en/latest/configuration.html

try:
    INVENIO_APP_RDM_VERSION = version("invenio-app-rdm")
except PackageNotFoundError:
    INVENIO_APP_RDM_VERSION = ""

APP_DEFAULT_SECURE_HEADERS = {
    "content_security_policy": {
        "default-src": [
            "'self'",
            "data:",  # for fonts
            "'unsafe-inline'",  # for inline scripts and styles
            "blob:",  # for pdf preview
            "s3.us-east-1.amazonaws.com",  # for S3 object storage
            "s3.eu-central-1.amazonaws.com",  # for S3 object storage
            # Add your own policies here (e.g. analytics)
        ],
        "img-src": [
            "*",
        ],
    },
    "force_https": True,
    "force_https_permanent": False,
    "force_file_save": False,
    "frame_options": "sameorigin",
    "frame_options_allow_from": None,
    "strict_transport_security": True,
    "strict_transport_security_preload": False,
    "strict_transport_security_max_age": 31556926,  # One year in seconds
    "strict_transport_security_include_subdomains": True,
    "content_security_policy_report_uri": None,
    "content_security_policy_report_only": False,
    "session_cookie_secure": True,
    "session_cookie_http_only": True,
}

SECURITY_POST_LOGOUT_VIEW = "/oauth/logout"
"""Redirect to this view after logout to properly clear the session.

/oauth/logout redirects on to the remote app's logout_url, the provider's
end_session_endpoint, so logging out here logs out of Keycloak or Authentik
too.
"""

# Redis/Valkey configuration
_redis_url = os.environ.get(
    "INVENIO_ACCOUNTS_SESSION_REDIS_URL", "redis://cache:6379/0"
)
# Extract base URL and database number
if "/" in _redis_url:
    _redis_base, _redis_db_str = _redis_url.rsplit("/", 1)
    try:
        _redis_db = int(_redis_db_str)
    except ValueError:
        _redis_db = 0
        _redis_base = _redis_url
else:
    _redis_base = _redis_url
    _redis_db = 0

# The full class path, as for Rogue Scholar: flask-caching 2 no longer
# resolves the short name "redis" (import of flask_caching.backends.redis).
CACHE_TYPE = "flask_caching.backends.RedisCache"
ACCOUNTS_SESSION_REDIS_URL = _redis_url
CELERY_BROKER_URL = f"{_redis_base}/{_redis_db + 1}"
BROKER_URL = f"{_redis_base}/{_redis_db + 1}"
CELERY_RESULT_BACKEND = f"{_redis_base}/{_redis_db + 2}"
RATELIMIT_STORAGE_URL = f"{_redis_base}/{_redis_db + 3}"
CACHE_REDIS_URL = f"{_redis_base}/{_redis_db + 4}"
COMMUNITIES_IDENTITIES_CACHE_REDIS_URL = f"{_redis_base}/{_redis_db + 4}"


# Flask-Babel
# ===========
# See https://python-babel.github.io/flask-babel/#configuration

# Default locale (language)
BABEL_DEFAULT_LOCALE = "en"
# Default time zone
BABEL_DEFAULT_TIMEZONE = "UTC"


# Invenio-I18N
# ============
# See https://invenio-i18n.readthedocs.io/en/latest/configuration.html

# Language name mapping for I18N configuration
_LANGUAGE_NAMES = {
    "de": _("German"),
    "es": _("Spanish"),
    "fr": _("French"),
    "it": _("Italian"),
    "pt": _("Portuguese"),
    "nl": _("Dutch"),
    "pl": _("Polish"),
    "ru": _("Russian"),
    "zh": _("Chinese"),
    "ja": _("Japanese"),
}

# Read languages from environment or use default list
_i18n_languages_str = os.environ.get("INVENIO_ISO639_LANGUAGES", "de,es,fr,pt")
_i18n_language_codes = [
    lang.strip() for lang in _i18n_languages_str.split(",") if lang.strip()
]

# Other supported languages (do not include BABEL_DEFAULT_LOCALE in list).
I18N_LANGUAGES = [
    (code, _LANGUAGE_NAMES.get(code, _(code.upper()))) for code in _i18n_language_codes
]

# Invenio-Mail
# ===========
# See https://invenio-mail.readthedocs.io/en/latest/configuration.html

# Set this to True to disable email sending.
MAIL_SUPPRESS_SEND = False

SECURITY_EMAIL_SUBJECT_REGISTER = _("Welcome to Invenio RDM Starter")
"""Email subject for account registration emails."""

# Invenio-Theme
# =============
# See https://invenio-theme.readthedocs.io/en/latest/configuration.html

# The name of the site to be used on the header and as a title.
THEME_SITENAME = "InvenioRDM Starter"
# Frontpage title
THEME_FRONTPAGE_TITLE = "InvenioRDM Starter"
# Frontpage subtitle
THEME_FRONTPAGE_SUBTITLE = (
    "A starter project for the turn-key research data management repository."
)
# Header logo
THEME_LOGO = "images/invenio-rdm-white.svg"

# Show the frontpage intro section
THEME_SHOW_FRONTPAGE_INTRO_SECTION = False


# Invenio-App-RDM
# ===============
# See https://invenio-app-rdm.readthedocs.io/en/latest/configuration.html

# Instance's theme entrypoint file. Path relative to the ``assets/`` folder.
INSTANCE_THEME_FILE = "./less/theme.less"

# Invenio-Files-Rest
# ==================

DATADIR = "/opt/invenio/var/instance/data"
"""The container directory where local files are stored."""

# Invenio-Assets
# ==============
# Use rspack instead of webpack
WEBPACKEXT_PROJECT = "invenio_assets.webpack:rspack_project"

# Invenio-Records-Resources
# =========================
# See https://github.com/inveniosoftware/invenio-records-resources/blob/master/invenio_records_resources/config.py

SITE_UI_URL = "https://localhost"

SITE_API_URL = "https://localhost/api"

APP_RDM_DEPOSIT_FORM_DEFAULTS = {
    "publication_date": lambda: datetime.now().strftime("%Y-%m-%d"),
    "rights": [
        {
            "id": "cc-by-4.0",
            "title": "Creative Commons Attribution 4.0 International",
            "description": (
                "The Creative Commons Attribution license allows "
                "re-distribution and re-use of a licensed work "
                "on the condition that the creator is "
                "appropriately credited."
            ),
            "link": "https://creativecommons.org/licenses/by/4.0/legalcode",
        }
    ],
    "resource_type": {
        "id": "publication-preprint",
    },
}

# See https://github.com/inveniosoftware/invenio-app-rdm/blob/master/invenio_app_rdm/config.py
APP_RDM_DEPOSIT_FORM_AUTOCOMPLETE_NAMES = "search"  # "search_only" or "off"
# Creators, affiliations and funders are suggested from the commonmeta store
# (invenio-pidbox), not from the names, affiliations and funders vocabularies.
APP_RDM_DEPOSIT_FORM_AUTOCOMPLETE_NAMES_PROVIDER = "pidbox"

# Invenio-Pidbox
# ==============
# The store (PIDBOX_SQLITE_PATH, default /var/lib/commonmeta/commonmeta.sqlite3,
# mounted from the host) answers for the vocabularies the Starter doesn't
# import: a record commit accepts any affiliation the store's ROR holds, and
# any funder ROR types as funder. The vocabularies still count where they have
# entries, so the accepted set is the union of the two.
PIDBOX_RECORD_RELATIONS = True

# Invenio-RDM-Records
# ===================

RDM_ALLOW_RESTRICTED_RECORDS = False
RDM_ALLOW_EXTERNAL_DOI_VERSIONING = False
"""Don't allow records with external DOIs to be versioned."""

#
# Persistent identifiers configuration
#
RDM_PERSISTENT_IDENTIFIER_PROVIDERS = [
    # DOI provider for externally managed DOIs
    providers.ExternalPIDProvider(
        "external",
        "doi",
        validators=[providers.BlockedPrefixes(config_names=["DATACITE_PREFIX"])],
        label=_("DOI"),
    ),
    # OAI identifier
    providers.OAIPIDProvider(
        "oai",
        label=_("OAI ID"),
    ),
]
"""A list of configured persistent identifier providers."""

RDM_PERSISTENT_IDENTIFIERS = {
    # DOI automatically removed if DATACITE_ENABLED is False.
    "doi": {
        "providers": ["external"],
        "required": False,
        "label": _("DOI"),
        "validator": idutils.is_doi,
        "normalizer": idutils.normalize_doi,
        "is_enabled": providers.ExternalPIDProvider.is_enabled,
        "ui": {"default_selected": "yes"},  # "yes", "no" or "not_needed"
    },
    "oai": {
        "providers": ["oai"],
        "required": True,
        "label": _("OAI"),
        "is_enabled": providers.OAIPIDProvider.is_enabled,
    },
}
"""The configured persistent identifiers for records."""

RDM_PARENT_PERSISTENT_IDENTIFIERS = {}
"""The configured persistent identifiers for parent records."""


def always_valid(identifier):
    """Gives every identifier as valid."""
    return True


RDM_RECORDS_IDENTIFIERS_SCHEMES = {
    "ark": {"label": _("ARK"), "validator": idutils.is_ark, "datacite": "ARK"},
    "arxiv": {
        "label": _("arXiv"),
        "validator": idutils.is_arxiv,
        "datacite": "arXiv",
    },
    "ads": {
        "label": _("Bibcode"),
        "validator": idutils.is_ads,
        "datacite": "bibcode",
    },
    "crossreffunderid": {
        "label": _("Crossref Funder ID"),
        "validator": always_valid,
        "datacite": "Crossref Funder ID",
    },
    "doi": {"label": _("DOI"), "validator": idutils.is_doi, "datacite": "DOI"},
    "ean13": {
        "label": _("EAN13"),
        "validator": idutils.is_ean13,
        "datacite": "EAN13",
    },
    "eissn": {
        "label": _("EISSN"),
        "validator": idutils.is_issn,
        "datacite": "EISSN",
    },
    "grid": {
        "label": _("GRID"),
        "validator": always_valid,
        "datacite": "GRID",
    },
    "handle": {
        "label": _("Handle"),
        "validator": idutils.is_handle,
        "datacite": "Handle",
    },
    "igsn": {
        "label": _("IGSN"),
        "validator": always_valid,
        "datacite": "IGSN",
    },
    "isbn": {
        "label": _("ISBN"),
        "validator": idutils.is_isbn,
        "datacite": "ISBN",
    },
    "isni": {
        "label": _("ISNI"),
        "validator": idutils.is_isni,
        "datacite": "ISNI",
    },
    "issn": {
        "label": _("ISSN"),
        "validator": idutils.is_issn,
        "datacite": "ISSN",
    },
    "istc": {
        "label": _("ISTC"),
        "validator": idutils.is_istc,
        "datacite": "ISTC",
    },
    "lissn": {
        "label": _("LISSN"),
        "validator": idutils.is_issn,
        "datacite": "LISSN",
    },
    "lsid": {
        "label": _("LSID"),
        "validator": idutils.is_lsid,
        "datacite": "LSID",
    },
    "pmid": {
        "label": _("PMID"),
        "validator": idutils.is_pmid,
        "datacite": "PMID",
    },
    "purl": {
        "label": _("PURL"),
        "validator": idutils.is_purl,
        "datacite": "PURL",
    },
    "upc": {"label": _("UPC"), "validator": always_valid, "datacite": "UPC"},
    "url": {"label": _("URL"), "validator": idutils.is_url, "datacite": "URL"},
    "urn": {"label": _("URN"), "validator": idutils.is_urn, "datacite": "URN"},
    "w3id": {
        "label": _("W3ID"),
        "validator": always_valid,
        "datacite": "w3id",
    },
    # Custom identifiers added for InvenioRDM Starter
    "uuid": {
        "label": _("UUID"),
        "validator": always_valid,
        "datacite": "UUID",
    },
    "guid": {
        "label": _("GUID"),
        "validator": always_valid,
        "datacite": "GUID",
    },
    "other": {
        "label": _("Other"),
        "validator": always_valid,
        "datacite": "Other",
    },
}
"""These are used for references, main, alternate and related identifiers."""

# DOI Registration
# =========================================================
# See https://inveniordm.docs.cern.ch/operate/customize/dois/

DATACITE_ENABLED = False
DATACITE_TEST_MODE = False
DATACITE_USERNAME = None
DATACITE_PASSWORD = None
DATACITE_PREFIX = None
DATACITE_DATACENTER_SYMBOL = None

# Invenio-S3
# ========================================================
# See https://inveniordm.docs.cern.ch/operate/customize/file-uploads/s3/
# Files are stored in S3 when an endpoint is configured, otherwise on the
# local disk (DATADIR).
if os.environ.get("INVENIO_S3_ENDPOINT_URL"):
    FILES_REST_STORAGE_FACTORY = s3fs_storage_factory


# Authentication
# =========================================================
# See https://inveniordm.docs.cern.ch/operate/customize/authentication/

# ACCOUNTS_LOCAL_LOGIN_ENABLED = True
"""Whether or not login with local account credentials should be enabled."""

# ACCOUNTS_DEFAULT_USER_VISIBILITY = "restricted"
"""Default User visibility value can be set to either 'restricted' or 'public'."""

# SECURITY_CHANGEABLE = True
"""Allow password change by users."""

# SECURITY_CONFIRMABLE = True
"""Allow user to confirm their email address."""

# SECURITY_RECOVERABLE = True
"""Allow password recovery by users."""

# SECURITY_REGISTERABLE = True
"""Allow users to register."""

# SECURITY_TRACKABLE = True
"""Enable user tracking on login."""

# SECURITY_LOGIN_WITHOUT_CONFIRMATION = True
"""Allow users to login without first confirming their email address."""


# Enable optional custom fields
RDM_NAMESPACES = {
    **JOURNAL_NAMESPACE,
    "rs": None,
}

RDM_CUSTOM_FIELDS = [
    *JOURNAL_CUSTOM_FIELDS,
]


RDM_CUSTOM_FIELDS_UI = [
    {
        "section": _("Publishing information"),
        "hide_from_landing_page": True,
        "fields": [
            # journal
            *JOURNAL_CUSTOM_FIELDS_UI["fields"],
        ],
    },
]

RDM_SORT_OPTIONS = {
    "bestmatch": dict(
        title=_("Best match"),
        fields=["_score"],
    ),
    "newest": dict(
        title=_("Newest"),
        fields=["-metadata.publication_date", "-metadata.dates.date"],
    ),
    "oldest": dict(
        title=_("Oldest"),
        fields=["metadata.publication_date", "metadata.dates.date"],
    ),
    "version": dict(
        title=_("Version"),
        fields=["-versions.index"],
    ),
    "updated-desc": dict(
        title=_("Recently updated"),
        fields=["-updated"],
    ),
    "updated-asc": dict(
        title=_("Least recently updated"),
        fields=["updated"],
    ),
    "created-desc": dict(
        title=_("Recently added"),
        fields=["-created"],
    ),
    "created-asc": dict(
        title=_("Least recently added"),
        fields=["created"],
    ),
    "mostviewed": dict(
        title=_("Most viewed"),
        fields=["-stats.all_versions.unique_views"],
    ),
    # The remaining options are InvenioRDM v14's own. RDM_SORT_OPTIONS also
    # serves the request searches (RDM_SEARCH_USER_REQUESTS), which sort by
    # activity: without newestactivity the record landing page, whose sidebar
    # builds the record's request search, fails with KeyError and shows
    # "Page not found".
    "mostdownloaded": dict(
        title=_("Most downloaded"),
        fields=["-stats.all_versions.unique_downloads"],
    ),
    "newestactivity": dict(
        title=_("Newest activity"),
        fields=["-last_activity_at"],
    ),
    "oldestactivity": dict(
        title=_("Oldest activity"),
        fields=["last_activity_at"],
    ),
}
"""Definitions of available record sort options."""


class DateHistogramFacet(LabelledFacetMixin, dsl.DateHistogramFacet):
    """Date Range Facet

    facets = {
        'publication_date': DateRangeFacet(
            field='dates',
            interval='year',
            format='yyyy'
        )
    }
    """

    def __init__(self, *args, **kwargs):
        """Show only years with at least 1 document, and at most 10 values."""
        kwargs.setdefault("min_doc_count", 1)
        super().__init__(*args, **kwargs)

    def get_value_filter(self, filter_value):
        """Overriding this function to cast string dates to datetime"""

        for interval_type in ("calendar_interval", "fixed_interval"):
            if interval_type in self._params:
                break
        else:
            interval_type = "interval"

        # dealing with a range
        try:
            if "--" in filter_value:
                start, end = [
                    datetime.strptime(year, "%Y") for year in filter_value.split("--")
                ]
                end = self.DATE_INTERVALS[self._params[interval_type]](end)
            else:
                start = datetime.strptime(filter_value, "%Y")
                end = self.DATE_INTERVALS[self._params[interval_type]](start)
        except ValueError:
            start = 0
            end = 1

        # swap them
        if start > end:
            start, end = end, start

        return dsl.query.Range(
            _expand__to_dot=False,
            **{
                self._params["field"]: {
                    "gte": start,
                    "lt": end,
                }
            },
        )


RDM_FACETS = {
    "access_status": {
        "facet": facets.access_status,
        "ui": {
            "field": "access.status",
        },
    },
    "is_published": {
        "facet": facets.is_published,
        "ui": {
            "field": "is_published",
        },
    },
    "file_type": {
        "facet": facets.filetype,
        "ui": {
            "field": "files.types",
        },
    },
    "language": {
        "facet": facets.language,
        "ui": {
            "field": "languages",
        },
    },
    "resource_type": {
        "facet": facets.resource_type,
        "ui": {
            "field": "resource_type.type",
            "childAgg": {
                "field": "resource_type.subtype",
            },
        },
    },
    "subject": {
        "facet": facets.subject,
        "ui": {
            "field": "subjects.subject",
        },
    },
    "publication_date": {
        "facet": DateHistogramFacet(
            field="metadata.publication_date_range",
            label=_("Publication year"),
            interval="year",
            format="yyyy",
        ),
        "ui": {"field": "publication_date"},
    },
    "affiliations": {
        "facet": TermsFacet(
            field="metadata.creators.affiliations.id",
            label=_("Author affiliations"),
            value_labels=StoreAffiliationsLabels("affiliations"),
        ),
        "ui": {
            "field": "metadata.creators.affiliations",
        },
    },
    "funders": {
        "facet": TermsFacet(
            field="metadata.funding.funder.id",
            label=_("Funders"),
            value_labels=StoreFundersLabels("funders"),
        ),
        "ui": {
            "field": "metadata.funding.funder",
        },
    },
    "author_identifiers": {
        "facet": TermsFacet(
            field="metadata.creators.person_or_org.identifiers.scheme",
            label=_("Author identifiers"),
            value_labels={"orcid": _("ORCID")},
        ),
        "ui": {
            "field": "metadata.creators.person_or_org.identifiers.scheme",
        },
    },
    "rights": {
        "facet": TermsFacet(
            field="metadata.rights.id",
            label=_("Licenses"),
            value_labels=VocabularyLabels("licenses"),
        ),
        "ui": {
            "field": "rights",
        },
    },
    "relations": {
        "facet": TermsFacet(
            field="metadata.related_identifiers.relation_type.id",
            label=_("Related works"),
            value_labels=VocabularyLabels("relationtypes"),
        ),
        "ui": {
            "field": "related_identifiers.relation_type",
        },
    },
    "references": {
        "facet": TermsFacet(
            field="metadata.references.scheme",
            label=_("References"),
            value_labels={
                "doi": _("DOI"),
                "url": _("URL"),
                "": _("No identifier"),
            },
        ),
        "ui": {
            "field": "metadata.references.scheme",
        },
    },
}


# from https://github.com/zenodo/zenodo-rdm/blob/master/site/zenodo_rdm/queryparser.py
def word_doi(node):
    """Quote DOIs."""
    if not node.value.startswith("10."):
        return node
    return Phrase(f'"{node.value}"')


def word_communities(node):
    """Resolve community slugs to IDs."""
    slug = node.value
    uuid = (
        db.session.query(CommunityMetadata.id)
        .filter(CommunityMetadata.slug == slug)
        .scalar()
    )
    return Phrase(f'"{uuid}"')


RDM_SEARCH = {
    # Supported values from RDM_FACETS
    "facets": [
        "language",
        "resource_type",
        "publication_date",
        "subject",
        "funders",
        "affiliations",
        "author_identifiers",
        "rights",
        "relations",
        "references",
    ],
    # Supported values from RDM_SORT_OPTIONS
    "sort": [
        "bestmatch",
        "newest",
        "oldest",
        "updated-desc",
        "updated-asc",
        "created-desc",
        "created-asc",
        "mostviewed",
    ],
    "query_parser_cls": QueryParser.factory(
        mapping={
            # shortcuts
            "title": "metadata.title",
            "subject": "metadata.subjects.subject",
            "contributor": "metadata.creators.person_or_org.name",
            "affiliation": "metadata.creators.affiliations.name",
            "funder": "metadata.funding.funder.name",
            "references": FieldValueMapper(
                "metadata.references.identifier", word=word_doi
            ),
            # taken from Zenodo
            "doi": FieldValueMapper("pids.doi.identifier", word=word_doi),
            "communities": FieldValueMapper(
                "parent.communities.ids", word=word_communities
            ),
            # Persistent identifiers
            "orcid": "metadata.creators.person_or_org.identifiers.identifier",
            "ror": "metadata.creators.affiliations.id",
            "issn": "custom_fields.journal:journal.issn",
        },
        tree_transformer_cls=SearchFieldTransformer,
    ),
}

COMMUNITIES_RECORDS_SEARCH = deepcopy(RDM_SEARCH)
"""Communities record search config is the same as the main record search."""

RDM_SEARCH_DRAFTS = {
    "facets": [
        "is_published",
        "language",
        "resource_type",
        "publication_date",
        "subject",
        "funders",
        "affiliations",
        "author_identifiers",
        "rights",
        "relations",
        "references",
    ],
    "sort": [
        "bestmatch",
        "newest",
        "oldest",
        "updated-desc",
        "updated-asc",
        "created-desc",
        "created-asc",
        "mostviewed",
    ],
}
"""User records search configuration (i.e. list of uploads)."""

# Toggle to show or hide the 'Browse' menu entry for communities.
COMMUNITIES_SHOW_BROWSE_MENU_ENTRY = True

# Enable featured communities
COMMUNITIES_ADMINISTRATION_DISABLED = False

# Authentication
# -------------------
# See https://github.com/inveniosoftware/invenio-oauthclient/blob/master/invenio_oauthclient/config.py

# ACCOUNTS_LOCAL_LOGIN_ENABLED = True
"""Whether or not login with local account credentials should be enabled."""

# ACCOUNTS_DEFAULT_USER_VISIBILITY = "restricted"
"""Default User visibility value can be set to either 'restricted' or 'public'."""

# OAUTHCLIENT_AUTO_REDIRECT_TO_EXTERNAL_LOGIN = True
"""Automatically redirect to external login provider."""

# SECURITY_CHANGEABLE = True
"""Allow password change by users."""

# SECURITY_CONFIRMABLE = True
"""Allow user to confirm their email address."""

# SECURITY_RECOVERABLE = True
"""Allow password recovery by users."""

# SECURITY_REGISTERABLE = True
"""Allow users to register."""

# SECURITY_TRACKABLE = True
"""Enable user tracking on login."""

# SECURITY_LOGIN_WITHOUT_CONFIRMATION = True
"""Allow users to login without first confirming their email address."""

# USERPROFILES_READ_ONLY = True
"""Make user profiles read-only, use values from OIDC."""

# OAUTHCLIENT_REMOTE_APPS is a *list* of RemoteApp objects, each carrying its
# own credentials; ext.py asserts isinstance(RemoteApp), so a dict fails at
# startup. The login page shows a button per app, in this order; with more
# than one, auto_redirect_login no longer redirects.
#
# Configured as for Rogue Scholar. Every OIDC provider uses
# invenio_rdm_starter.oidc.OAuthClientRemoteApp, the authlib branch's
# OIDCRemoteApp with verified email addresses only, usr_xxxxxxxx usernames and
# ORCID iDs linked. Each is configured only when its issuer or client id is
# set. The issuer, without a trailing slash, gives the discovery document,
# <issuer>/.well-known/openid-configuration, and the logout URL, its
# end_session_endpoint; server_metadata and logout_url override them.
#
# Defaults, each overridden by passing it:
#   scope - "openid email profile" (GitHubRemoteApp: "read:user user:email")
#   title - the name capitalized, ORCID and GitHub as they spell themselves
#   icon  - static/images/<name>.svg
#
# Credentials come from
#   INVENIO_<NAME>_CLIENT_ID - client id
#   INVENIO_<NAME>_CLIENT_SECRET - client secret
# authlib's names for them, where <NAME> is the provider: KEYCLOAK, AUTHENTIK,
# ORCID, GITHUB, GOOGLE, DISCORD (see invenio_rdm_starter.oidc.
# client_credentials). The app's name, the provider's in lower case, is in its
# redirect URI, https://<site>/oauth/authorized/<name>, registered without a
# trailing slash, and is the method of its linked accounts: renaming an app
# breaks both.
#
# Credentials are read from the environment directly rather than left to
# invenio-config: every INVENIO_-prefixed variable goes through
# ast.literal_eval on the way into the config, which turns an all-digit client
# id into an int. ORCID gets the client secret in the token request body
# (client_secret_post), the only method it accepts, and so does GitHub, which
# GitHubRemoteApp sets; the others in an Authorization header, authlib's
# default.
OAUTHCLIENT_REMOTE_APPS: list = []

# Keycloak configuration.
if _issuer := os.environ.get("INVENIO_KEYCLOAK_ISSUER"):
    _client_id, _client_secret = client_credentials("keycloak", required=True)
    OAUTHCLIENT_REMOTE_APPS.append(
        OAuthClientRemoteApp(
            name="keycloak",
            issuer=_issuer,
            client_id=_client_id,
            client_secret=_client_secret,
        )
    )

# Authentik configuration
# Its email scope mapping must send email_verified from the user attribute
# the enrollment flow sets; Authentik's default mapping always sends false.
# The orcid scope asks for the ORCID iD of the user's ORCID source connection,
# which an orcid scope mapping on the provider sends as the orcid claim:
# OAuthClientRemoteApp links it to the account.
if _issuer := os.environ.get("INVENIO_AUTHENTIK_ISSUER"):
    _client_id, _client_secret = client_credentials("authentik", required=True)
    OAUTHCLIENT_REMOTE_APPS.append(
        OAuthClientRemoteApp(
            name="authentik",
            issuer=_issuer,
            client_id=_client_id,
            client_secret=_client_secret,
            scope="openid email profile orcid",
        )
    )

# ORCID, whose subject is the ORCID iD. It offers only the openid scope and
# sends no email address: a new user types one into the signup form.
#   INVENIO_ORCID_ISSUER - optional, default https://orcid.org; use
#       https://sandbox.orcid.org with a sandbox client
if client_credentials("orcid")[0]:
    _client_id, _client_secret = client_credentials("orcid", required=True)
    OAUTHCLIENT_REMOTE_APPS.append(
        OAuthClientRemoteApp(
            name="orcid",
            issuer=os.environ.get("INVENIO_ORCID_ISSUER") or "https://orcid.org",
            client_id=_client_id,
            client_secret=_client_secret,
            scope="openid",
            client_kwargs={"token_endpoint_auth_method": "client_secret_post"},
            orcid_claim="sub",
        )
    )

# GitHub configuration. GitHub doesn't support OIDC, the GitHubRemoteApp uses OAuth2
# The scope is read:user user:email: the profile and the email addresses, read-only.
if client_credentials("github")[0]:
    _client_id, _client_secret = client_credentials("github", required=True)
    OAUTHCLIENT_REMOTE_APPS.append(
        GitHubRemoteApp(
            name="github",
            client_id=_client_id,
            client_secret=_client_secret,
        )
    )

# Google and Discord. Discord's discovery document lists no scopes: identify
# is its scope for the user's name, email for the address.
if client_credentials("google")[0]:
    _client_id, _client_secret = client_credentials("google", required=True)
    OAUTHCLIENT_REMOTE_APPS.append(
        OAuthClientRemoteApp(
            name="google",
            issuer="https://accounts.google.com",
            client_id=_client_id,
            client_secret=_client_secret,
        )
    )

if client_credentials("discord")[0]:
    _client_id, _client_secret = client_credentials("discord", required=True)
    OAUTHCLIENT_REMOTE_APPS.append(
        OAuthClientRemoteApp(
            name="discord",
            issuer="https://discord.com",
            client_id=_client_id,
            client_secret=_client_secret,
            scope="openid identify email",
        )
    )

ACCOUNTS_LOGIN_VIEW_FUNCTION = (
    auto_redirect_login  # autoredirect to external login if enabled
)
OAUTHCLIENT_AUTO_REDIRECT_TO_EXTERNAL_LOGIN = False  # autoredirect to external login
# The signup form after an OAuth login asks for what the remote app did not
# send: email marked required, username read-only. See
# invenio_rdm_starter.oidc.signup_form.
OAUTHCLIENT_SIGNUP_FORM = signup_form

OAUTHCLIENT_STATE_EXPIRES = 1800
"""Seconds after which the state token generated for OIDC authentication
expires (default 3600). Should be higher than the validity the OIDC provider
gives the authentication request (e.g. 900 seconds)."""

USERPROFILES_READ_ONLY = True

# OAI-PMH
# =======
# See https://github.com/inveniosoftware/invenio-oaiserver/blob/master/invenio_oaiserver/config.py

OAISERVER_ID_PREFIX = "invenio-rdm"
"""The prefix that will be applied to the generated OAI-PMH ids."""

# Invenio-Search
# --------------

SEARCH_INDEX_PREFIX = "invenio-rdm-"

# Citation style name mapping
# ------------------------------------------
# See https://inveniordm.docs.cern.ch/operate/customize/configuration/#citation-styles

_CITATION_STYLE_NAMES = {
    "apa": _("APA"),
    "harvard-cite-them-right": _("Harvard"),
    "ieee": _("IEEE"),
    "modern-language-association": _("MLA"),
    "vancouver": _("Vancouver"),
    "chicago-author-date": _("Chicago"),
    "chicago-note-bibliography": _("Chicago (Notes)"),
    "nature": _("Nature"),
    "science": _("Science"),
}

# Read citation styles from environment or use default list
_rdm_citation_styles_str = os.environ.get(
    "INVENIO_RDM_CITATION_STYLES",
    "apa,harvard-cite-them-right,ieee,modern-language-association,vancouver,chicago-author-date",
)
_rdm_citation_style_codes = [
    style.strip() for style in _rdm_citation_styles_str.split(",") if style.strip()
]

RDM_CITATION_STYLES = [
    (code, _CITATION_STYLE_NAMES.get(code, _(code.replace("-", " ").title())))
    for code in _rdm_citation_style_codes
]
"""The list of enabled citation styles."""

RDM_CITATION_STYLES_DEFAULT = (
    _rdm_citation_style_codes[0] if _rdm_citation_style_codes else None
)
"""The default citation style."""

# Redirection of legacy URLs
# --------------------------

REDIRECTOR_RULES = {
    # "redirect_name": {
    #     "source": "/old_about",
    #     "target": "/about",
    # },
}


"""InvenioRDM Starter permissions.
These permissions are restrictive and only allow admin users to manage records."""

# these are defined here as there is a circular dependency otherwise with the
# permissions.py file
media_files_management_action = action_factory("manage-media-files")


class MediaFilesManager(Generator):
    """Allows media files management."""

    def __init__(self):
        """Constructor."""
        super(MediaFilesManager, self).__init__()

    def needs(self, **kwargs):
        """Enabling Needs."""
        return [media_files_management_action]


class IfRecordManagementAllowedForCommunity(ConditionalGenerator):
    """Conditional generator for community access to record management."""

    def _condition(self, record, **kwargs):
        """Check if community can manage the migrated record."""
        if record is None:
            return False
        try:
            can_community_manage_record = dict_lookup(
                record.parent, "permission_flags.can_community_manage_record"
            )
        except KeyError:
            can_community_manage_record = True

        return can_community_manage_record

    def query_filter(self, **kwargs):
        """Filters for current identity as super user."""
        then_query = self._make_query(self.then_, **kwargs)
        else_query = self._make_query(self.else_, **kwargs)

        return then_query if then_query else else_query


class StarterRecordPermissionPolicy(RDMRecordPermissionPolicy):
    """Access control configuration for records."""

    #
    # High-level permissions (used by low-level)
    #
    can_manage = [
        IfRecordManagementAllowedForCommunity(
            then_=RDMRecordPermissionPolicy.can_manage,
            else_=[
                RecordOwners(),
                AccessGrant("manage"),
                SystemProcess(),
            ],
        )
    ]
    can_curate = can_manage + [SystemProcess()]
    can_review = can_curate + [SystemProcess()]
    can_preview = can_curate + [SystemProcess()]

    #
    #  Records
    #

    # Used for search filtering of deleted records
    # cannot be implemented inside can_read - otherwise permission will
    # kick in before tombstone renders
    can_create = [SystemProcess()]
    can_read_deleted = [SystemProcess()]
    can_read_deleted_files = can_read_deleted
    can_media_read_deleted_files = can_read_deleted_files

    #
    # Drafts
    #
    # Allow reading metadata of a draft
    can_read_draft = can_preview
    # Allow reading files of a draft
    can_draft_read_files = can_preview + [SystemProcess()]
    # Allow updating metadata of a draft
    can_update_draft = can_review
    # Allow uploading, updating and deleting files in drafts
    can_draft_create_files = can_review
    can_draft_set_content_files = [SystemProcess()]
    can_draft_get_content_files = [SystemProcess()]
    can_draft_commit_files = [SystemProcess()]
    can_draft_update_files = can_review
    can_draft_delete_files = can_review
    can_manage_record_access = can_review

    #
    # PIDs
    #
    can_pid_create = can_review
    can_pid_register = can_review
    can_pid_update = can_review
    can_pid_discard = can_review
    can_pid_delete = can_review

    #
    # Actions
    #
    # Allow to put a record in edit mode (create a draft from record)
    can_edit = [SystemProcess()]
    # Allow deleting/discarding a draft and all associated files
    can_delete_draft = [SystemProcess()]
    # Allow creating a new version of an existing published record.
    can_new_version = [SystemProcess()]
    # Allow publishing a new record or changes to an existing record.
    can_publish = [SystemProcess()]
    # Allow lifting a record or draft.
    can_lift_embargo = [SystemProcess()]

    #
    # Record communities
    #
    # Who can add record to a community
    can_add_community = can_review

    # Media files
    can_draft_media_create_files = [MediaFilesManager(), SystemProcess()]
    can_draft_media_read_files = can_draft_media_create_files
    can_draft_media_set_content_files = [SystemProcess()]
    can_draft_media_commit_files = [SystemProcess()]
    can_draft_media_update_files = can_draft_media_create_files
    can_draft_media_delete_files = can_draft_media_create_files
    can_moderate = [SystemProcess()]
    can_media_create_files = [SystemProcess()]
    can_media_set_content_files = [SystemProcess()]
    can_media_commit_files = [SystemProcess()]
    can_media_update_files = [SystemProcess()]
    can_media_delete_files = [SystemProcess()]
    can_modify_locked_files = [SystemProcess()]


class StarterCommunityPermissionPolicy(CommunityPermissionPolicy):
    """Permissions for Community CRUD operations.
    We start with limited permissions for community creation and moderation.
    """

    can_create = [SystemProcess()]
    can_moderate = [SystemProcess()]
    can_rename = [SystemProcess()]
    can_submit_record = [SystemProcess()]
    can_include_directly = [SystemProcess()]


RDM_PERMISSION_POLICY = StarterRecordPermissionPolicy
"""InvenioRDM Starter record permission policy."""

COMMUNITIES_ALLOW_RESTRICTED = False
"""Don't allow restricted records in communities."""

COMMUNITIES_PERMISSION_POLICY = StarterCommunityPermissionPolicy
"""InvenioRDM Starter community permission policy."""
