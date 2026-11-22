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
import re
from urllib.parse import urlparse
from copy import deepcopy
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import cast
import idutils
from invenio_rdm_records.services.pids import providers
from invenio_rdm_records.contrib import journal
from invenio_records_resources.services.records.queryparser import (
    FieldValueMapper,
    QueryParser,
    SearchFieldTransformer,
)
from invenio_records_resources.services.records.facets.facets import (
    TermsFacet,
)

# invenio-oauthclient comes from the max-moser/invenio-oauthclient mm/authlib
# branch, a rewrite on authlib, as for Rogue Scholar. See the Authentication
# section.
from invenio_oauthclient.views.views import auto_redirect_login
from invenio_rdm_starter import custom_fields
from invenio_rdm_starter.permissions import (
    StarterCommunityPermissionPolicy,
    StarterRecordPermissionPolicy,
)
from invenio_rdm_starter.queryparser import word_communities, word_doi
from invenio_rdm_starter.oidc import (
    GitHubRemoteApp,
    OAuthClientRemoteApp,
    client_credentials,
    signup_form,
)
from invenio_app import config as invenio_app_config
from invenio_rdm_records import config as rdm_config
from invenio_pidbox import custom_fields as pidbox_fields
from invenio_pidbox.components import citations_components
from invenio_pidbox.facets import StoreAffiliationsLabels, StoreFundersLabels
from invenio_vocabularies.services.facets import VocabularyLabels
from invenio_s3 import s3fs_storage_factory

INVENIO_RDM_STARTER_CONFIG_MODULE = __name__
"""Which module these settings came from. invenio_rdm_starter.views refuses to
start without it: if the package is installed without its
invenio_config.module entry point (e.g. a venv not synced since the entry
point was added), the app would otherwise run on InvenioRDM's defaults
without saying so."""


def _(x):  # needed to avoid start time failure with lazy strings
    return x


# Redis/Valkey
# ============
# Connection URLs for the cache, sessions, Celery and rate limits, which the
# sections below use: one Redis/Valkey server, one database number each.

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


# Flask-Limiter
# =============
# See https://flask-limiter.readthedocs.io/en/stable/configuration.html

RATELIMIT_STORAGE_URL = f"{_redis_base}/{_redis_db + 3}"
"""Where the rate limit counters are kept: Redis/Valkey database + 3."""


# Invenio-I18N
# ============
# See https://invenio-i18n.readthedocs.io/en/latest/configuration.html

# Language name mapping for I18N configuration
_language_names = {
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

I18N_LANGUAGES = [
    (code, _language_names.get(code, _(code.upper()))) for code in _i18n_language_codes
]
"""Other supported languages (do not include BABEL_DEFAULT_LOCALE in list)."""


# Invenio-Files-REST / Invenio-S3
# ===============================
# See https://inveniordm.docs.cern.ch/operate/customize/file-uploads/s3/

# Files are stored in S3 when an endpoint is configured, otherwise on the
# local disk (InvenioRDM's default files location).
if os.environ.get("INVENIO_S3_ENDPOINT_URL"):
    FILES_REST_STORAGE_FACTORY = s3fs_storage_factory


# Invenio-Accounts
# ================
# See https://inveniordm.docs.cern.ch/operate/customize/authentication/
# Login is through OAuth (Invenio-OAuthClient below). Local login, registration,
# password and confirmation settings come from the environment, documented in
# compose.yml (x-set-authentication).

SECURITY_EMAIL_SUBJECT_REGISTER = _("Welcome to Invenio RDM Starter")
"""Email subject for account registration emails."""

SECURITY_POST_LOGOUT_VIEW = "/oauth/logout"
"""Redirect to this view after logout to properly clear the session.

/oauth/logout redirects on to the remote app's logout_url, the provider's
end_session_endpoint, so logging out here logs out of Keycloak or Authentik
too."""

ACCOUNTS_LOGIN_VIEW_FUNCTION = (
    auto_redirect_login  # autoredirect to external login if enabled
)
"""The login view. It redirects straight to the external login when
OAUTHCLIENT_AUTO_REDIRECT_TO_EXTERNAL_LOGIN is on and there is a
single OAuth provider."""


# Invenio-OAuthClient
# ===================
# See https://github.com/inveniosoftware/invenio-oauthclient/blob/master/invenio_oauthclient/config.py

OAUTHCLIENT_REMOTE_APPS: list = []
"""OAUTHCLIENT_REMOTE_APPS is a *list* of RemoteApp objects, each carrying its
own credentials; ext.py asserts isinstance(RemoteApp), so a dict fails at
startup. The login page shows a button per app, in this order; with more
than one, auto_redirect_login no longer redirects.
Configured as for Rogue Scholar. Every OIDC provider uses
invenio_rdm_starter.oidc.OAuthClientRemoteApp, the authlib branch's
OIDCRemoteApp with verified email addresses only, usr_xxxxxxxx usernames and
ORCID iDs linked. Each is configured only when its issuer or client id is
set. The issuer, without a trailing slash, gives the discovery document,
<issuer>/.well-known/openid-configuration, and the logout URL, its
end_session_endpoint; server_metadata and logout_url override them.
Defaults, each overridden by passing it:
  scope - "openid email profile" (GitHubRemoteApp: "read:user user:email")
  title - the name capitalized, ORCID and GitHub as they spell themselves
  icon  - static/images/<name>.svg
Credentials come from
  INVENIO_<NAME>_CLIENT_ID - client id
  INVENIO_<NAME>_CLIENT_SECRET - client secret
authlib's names for them, where <NAME> is the provider: KEYCLOAK, AUTHENTIK,
ORCID, GITHUB, GOOGLE, DISCORD (see invenio_rdm_starter.oidc.
client_credentials). The app's name, the provider's in lower case, is in its
redirect URI, https://<site>/oauth/authorized/<name>, registered without a
trailing slash, and is the method of its linked accounts: renaming an app
breaks both.
Credentials are read from the environment directly rather than left to
invenio-config: every INVENIO_-prefixed variable goes through
ast.literal_eval on the way into the config, which turns an all-digit client
id into an int. ORCID gets the client secret in the token request body
(client_secret_post), the only method it accepts, and so does GitHub, which
GitHubRemoteApp sets; the others in an Authorization header, authlib's
default."""

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

OAUTHCLIENT_SIGNUP_FORM = signup_form
"""The signup form after an OAuth login asks for what the remote app did not
send: email marked required, username read-only. See
invenio_rdm_starter.oidc.signup_form."""

OAUTHCLIENT_STATE_EXPIRES = 1800
"""Seconds after which the state token generated for OIDC authentication
expires (default 3600). Should be higher than the validity the OIDC provider
gives the authentication request (e.g. 900 seconds)."""


# Invenio-Celery
# ==============

CELERY_BROKER_URL = f"{_redis_base}/{_redis_db + 1}"
"""Celery's message broker: Redis/Valkey database + 1."""

BROKER_URL = f"{_redis_base}/{_redis_db + 1}"
"""Celery's message broker, under Celery's older setting name."""

CELERY_RESULT_BACKEND = f"{_redis_base}/{_redis_db + 2}"
"""Where Celery keeps task results: Redis/Valkey database + 2."""


# Invenio-Jobs
# ============

JOBS_DEFAULT_QUEUE = "low"
"""The queue a job created in the Jobs dashboard runs on, unless changed there.

Jobs are long runs (imports, citation refreshes, community updates), so they
go to the low priority queue, which the ``worker-low`` service of compose.yml
takes with a few processes of its own. The ``worker`` service keeps the
default queue, ``celery``, free for the short tasks a request starts. Jobs
created with ``invenio jobs create`` still get ``celery``: invenio-jobs's
command line sets it.
"""


# Flask-Caching
# =============

CACHE_REDIS_URL = f"{_redis_base}/{_redis_db + 4}"
"""The application cache: Redis/Valkey database + 4."""


# Invenio-Assets
# ==============

WEBPACKEXT_PROJECT = "invenio_assets.webpack:rspack_project"
"""Use rspack instead of webpack."""


# Invenio-App
# ===========
# See https://invenio-app.readthedocs.io/en/latest/configuration.html

try:
    INVENIO_APP_RDM_VERSION = version("invenio-app-rdm")
except PackageNotFoundError:
    INVENIO_APP_RDM_VERSION = ""


def s3_endpoint_sources(endpoint_url: str | None) -> list[str]:
    """The host of the S3 endpoint the files are served from, for the CSP.

    InvenioRDM answers a file download with a link signed for the bucket's
    endpoint, which the browser fetches (the PDF preview among them): with
    Hetzner's https://fsn1.your-objectstorage.com, fsn1.your-objectstorage.com.
    Nothing without an endpoint, as with files on disk.
    """
    host = urlparse(endpoint_url or "").netloc
    return [host] if host else []


APP_DEFAULT_SECURE_HEADERS = {
    **invenio_app_config.APP_DEFAULT_SECURE_HEADERS,
    "content_security_policy": {
        **cast(
            dict[str, list[str]],
            invenio_app_config.APP_DEFAULT_SECURE_HEADERS["content_security_policy"],
        ),
        "default-src": [
            "'self'",
            "data:",  # for fonts
            "'unsafe-inline'",  # for inline scripts and styles
            "blob:",  # for pdf preview
            "s3.us-east-1.amazonaws.com",  # for S3 object storage
            "s3.eu-central-1.amazonaws.com",  # for S3 object storage
            # The configured S3 endpoint's signed file links.
            *s3_endpoint_sources(os.environ.get("INVENIO_S3_ENDPOINT_URL")),
            # Add your own policies here (e.g. analytics)
        ],
        "img-src": [
            "*",
        ],
    },
}
"""invenio-app's secure headers. Its Content Security Policy is extended with the
sources the Starter needs; the rest, object-src 'none' among it, is
invenio-app's, as are HTTPS, HSTS, frame options and cookies."""


# Invenio-Theme
# =============

THEME_LOGO = "images/starter-white.svg"
"""The menubar's logo: InvenioRDM's own, under the name deployments already
set (INVENIO_THEME_LOGO replaces it). The Starter marks itself with an amber
"STARTER" ribbon across the menubar's top-left corner instead, in the
theme's site.overrides. The menubar of invenio-app-rdm and of the
administration panel shows THEME_LOGO."""


# Front page
# ==========

STARTER_FRONTPAGE_ABOUT_PAGE = None
"""The page whose content is a box at the top of the front page, above the
metrics (invenio_rdm_starter/header_frontpage.html): what the repository
holds, e.g. "/about". Admins edit it under Site management > Pages, in each
language. None, as now, or without the page, there is no box; and with the
metrics off either, the front page has the plain header, the Starter Packs
following the menubar."""

STARTER_FRONTPAGE_SIDEBAR_PAGES = ["/about/why"]
"""The pages shown as boxes of the front page's sidebar, in this order: the
page's title as the header, its content as the box (invenio_rdm_starter.
pages). Admins edit them under Site management > Pages. A page that doesn't
exist is left out. The Starter's pages are app_data/pages.yaml."""

STARTER_FRONTPAGE_FEATURED_TITLE = None
"""The heading of the front page's carousel of featured communities, which
are the Starter Packs (invenio_rdm_starter.starter_packs); translated where
the Starter's catalogs have it. None, as now: InvenioRDM's, "Featured
communities"."""

STARTER_PACKS_FILE = None
"""The file the Starter Packs are defined in, each a community that the "Sync
starter packs" job creates
(invenio_rdm_starter.starter_packs); app_data/starter_packs.yaml of the
instance unless set."""


# Starting afresh
# ===============

STARTER_DELETE_ALL_RECORDS_ENABLED = False
"""Whether the "Delete all records" job may run (invenio_rdm_starter.reset).

It deletes every record, with its drafts, versions, requests and PIDs, for a
demo instance whose records are imported and imported again at will. Off, so
that an instance with data of its own never loses it; a demo sets
INVENIO_STARTER_DELETE_ALL_RECORDS_ENABLED=True. Refused all the same where a
DOI was minted here."""


# Invenio-App-RDM
# ===============
# See https://github.com/inveniosoftware/invenio-app-rdm/blob/master/invenio_app_rdm/config.py

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
"""What a new upload starts with: today's date, the CC BY 4.0 license
and the resource type preprint."""

APP_RDM_DEPOSIT_FORM_AUTOCOMPLETE_NAMES_PROVIDER = "pidbox"
"""Creators, affiliations and funders are suggested from the commonmeta store
(invenio-pidbox), not from the names, affiliations and funders vocabularies."""

_citation_style_names = {
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

# Read citation styles from the environment, as in compose.yml. Not from
# INVENIO_RDM_CITATION_STYLES: invenio-config would write that variable's raw
# string over RDM_CITATION_STYLES, and the landing page's citation box would get
# a string instead of the list built here.
_rdm_citation_styles_str = os.environ.get(
    "INVENIO_RDM_CITATION_STYLES_LIST",
    "apa,chicago-author-date,harvard-cite-them-right,ieee,vancouver",
)

_rdm_citation_style_codes = [
    style.strip() for style in _rdm_citation_styles_str.split(",") if style.strip()
]

RDM_CITATION_STYLES = [
    (code, _citation_style_names.get(code, _(code.replace("-", " ").title())))
    for code in _rdm_citation_style_codes
]
"""The list of enabled citation styles."""

REDIRECTOR_RULES = {
    # "redirect_name": {
    #     "source": "/old_about",
    #     "target": "/about",
    # },
}
"""Redirects of legacy URLs (invenio-app-rdm's redirector); none so far."""


# Invenio-Communities
# ===================

COMMUNITIES_IDENTITIES_CACHE_REDIS_URL = f"{_redis_base}/{_redis_db + 4}"
"""Cache of community membership identities: Redis/Valkey
database + 4, shared with the application cache."""

COMMUNITIES_ALLOW_RESTRICTED = False
"""Don't allow restricted records in communities."""

COMMUNITIES_PERMISSION_POLICY = StarterCommunityPermissionPolicy
"""InvenioRDM Starter community permission policy."""


# Invenio-RDM-Records
# ===================
# See https://github.com/inveniosoftware/invenio-rdm-records/blob/master/invenio_rdm_records/config.py
# DOI registration: https://inveniordm.docs.cern.ch/operate/customize/dois/

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
    **rdm_config.RDM_PERSISTENT_IDENTIFIERS,
    "doi": {
        "providers": ["external"],
        "required": False,
        "label": _("DOI"),
        "validator": idutils.is_doi,
        "normalizer": idutils.normalize_doi,
        "is_enabled": providers.ExternalPIDProvider.is_enabled,
        "ui": {"default_selected": "yes"},  # "yes", "no" or "not_needed"
    },
}
"""The configured persistent identifiers for records.

InvenioRDM's persistent identifiers, with a DOI of the Starter's own: an
existing DOI the depositor brings (external), never one minted here, and not
required. OAI identifiers are InvenioRDM's."""

RDM_PARENT_PERSISTENT_IDENTIFIER_PROVIDERS = [
    providers.ExternalPIDProvider("external", "doi", label=_("Concept DOI")),
]
"""The parent records' DOI: a concept DOI from elsewhere, never one minted
here."""

RDM_PARENT_PERSISTENT_IDENTIFIERS = {
    "doi": {
        "providers": ["external"],
        "required": False,
        # Never minted on publishing: invenio-pidbox's import sets it.
        "condition": lambda record: False,
        "label": _("Concept DOI"),
        "validator": idutils.is_doi,
        "normalizer": idutils.normalize_doi,
        "is_enabled": providers.ExternalPIDProvider.is_enabled,
    },
}
"""The configured persistent identifiers for parent records.

The concept DOI of a work's versions, as on Zenodo: invenio-pidbox's import
puts a version's IsVersionOf DOI on its parent, which "Cite all versions"
shows. Never minted on publishing, and set only by the import; but a parent
with one needs the provider, or publishing its next version fails."""


def is_openalex_work(value: str) -> bool:
    """Whether ``value`` is an OpenAlex work ID, as a URL or bare (W123)."""
    return re.fullmatch(r"(?:https://openalex\.org/)?W\d+", value or "") is not None


RDM_RECORDS_IDENTIFIERS_SCHEMES = {
    scheme: definition
    for scheme, definition in rdm_config.RDM_RECORDS_IDENTIFIERS_SCHEMES.items()
    if scheme != "other"
}
"""InvenioRDM's schemes, extended rather than copied, so that the schemes a
release adds arrive with it: a copy from before v14 had left out CSTR, RRID
and Wikidata. The Starter adds UUID, GUID and OpenAlex (a work's OpenAlex ID,
which commonmeta's OpenAlex enrichment adds), and keeps "other" last."""
RDM_RECORDS_IDENTIFIERS_SCHEMES.update(
    {
        "uuid": {
            "label": _("UUID"),
            "validator": rdm_config.always_valid,
            "datacite": "UUID",
        },
        "guid": {
            "label": _("GUID"),
            "validator": rdm_config.always_valid,
            "datacite": "GUID",
        },
        "openalex": {
            "label": "OpenAlex",
            "validator": is_openalex_work,
            "datacite": "Other",
        },
        "other": rdm_config.RDM_RECORDS_IDENTIFIERS_SCHEMES["other"],
    }
)
"""These are used for references, main, alternate and related identifiers."""

RDM_NAMESPACES = {
    **journal.JOURNAL_NAMESPACE,
    **pidbox_fields.PIDBOX_NAMESPACE,
}
"""Namespaces of the custom fields: the journal fields, and invenio-pidbox's
citations."""

RDM_CUSTOM_FIELDS = [
    *journal.JOURNAL_CUSTOM_FIELDS,
    *pidbox_fields.CITATIONS_CUSTOM_FIELDS,
]
"""Custom fields of records: the journal fields, and `pidbox:citations`, the
works citing a record. invenio-pidbox fills it in from the commonmeta store
with the "Refresh citations" job (Administration → Jobs); nobody edits it, so
the deposit form doesn't show it. The landing page lists the citations, and
the person and organization pages count the cited works."""

COMMUNITIES_NAMESPACES = custom_fields.RS_NAMESPACE
"""The namespace of the communities' custom fields: rs, as Rogue Scholar's."""

COMMUNITIES_CUSTOM_FIELDS = custom_fields.STARTER_PACK_CUSTOM_FIELDS
"""Custom fields of communities: what a Starter Pack holds, by ISSN, DOI
prefix, language and license (invenio_rdm_starter.custom_fields). Their
mappings are created by `invenio communities custom-fields init`, which the
setup runs; an instance set up before them needs it run once."""

COMMUNITIES_CUSTOM_FIELDS_UI = [custom_fields.STARTER_PACK_CUSTOM_FIELDS_UI]
"""The Starter Pack section of a community's settings."""

RDM_CUSTOM_FIELDS_UI = [
    {
        "section": _("Publishing information"),
        "hide_from_landing_page": True,
        "fields": [
            # journal
            *journal.JOURNAL_CUSTOM_FIELDS_UI["fields"],
        ],
    },
]
"""The deposit form section of the journal fields, which the landing
page doesn't show."""

RDM_SORT_OPTIONS = {
    **rdm_config.RDM_SORT_OPTIONS,
    "newest": {
        "title": _("Newest"),
        "fields": ["-metadata.publication_date", "-metadata.dates.date"],
    },
    "oldest": {
        "title": _("Oldest"),
        "fields": ["metadata.publication_date", "metadata.dates.date"],
    },
    "created-desc": {
        "title": _("Recently added"),
        "fields": ["-created"],
    },
    "created-asc": {
        "title": _("Least recently added"),
        "fields": ["created"],
    },
}
"""Definitions of available record sort options.

InvenioRDM's sort options, extended rather than copied. RDM_SORT_OPTIONS also
serves the request searches (RDM_SEARCH_USER_REQUESTS sorts by activity), and
a copy from before v14 without newestactivity made every record landing page
fail with KeyError, shown as "Page not found". The Starter sorts newest and
oldest by publication date rather than by when the record was created, and
adds sorting by creation date as options of its own."""

RDM_FACETS = {
    **rdm_config.RDM_FACETS,
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
    "citations": pidbox_fields.CITATIONS_FACET,
    "content": {
        # The records with a PDF among their files, which invenio-pidbox's
        # Attach PDFs job adds, and those with a ZIP, the software archives
        # its Attach software archives job adds; other file types aren't
        # offered.
        "facet": TermsFacet(
            field="files.types",
            label=_("Content"),
            value_labels={"pdf": "PDF", "zip": "ZIP"},
            include=["pdf", "zip"],
        ),
        "ui": {
            "field": "files.types",
        },
    },
}
"""InvenioRDM's facets, extended rather than copied, so that the facets a
release adds arrive with it, InvenioRDM v14's publication date facet among
them. The Starter adds facets for affiliations, funders, author identifiers,
licenses, related works, references, citations and content (records with a
PDF or a ZIP)."""

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
        "citations",
        "content",
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
            "citations": pidbox_fields.CITATIONS_QUERY_FIELD,
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
"""Search of published records: the facets and sort options it offers,
and the query parser with the Starter's field shortcuts."""

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
        "citations",
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

RDM_PERMISSION_POLICY = StarterRecordPermissionPolicy
"""InvenioRDM Starter record permission policy."""

RDM_COMMUNITY_REQUIRED_TO_PUBLISH = True
"""A record belongs to a community: the deposit form asks for one before it
publishes, and a record's last community can't be removed, except by an
administrator or the system. The Starter's records come in through
invenio-pidbox's imports, which publish as the system, which InvenioRDM
exempts; so the imports refuse a run that names no community (invenio-pidbox,
the release after 0.7.11), and their Community select offers only the Starter
Packs (PIDBOX_JOBS_COMMUNITY_TYPES): every record imported joins one."""

RDM_RECORDS_SERVICE_COMPONENTS = citations_components()
"""InvenioRDM's record service components, with the one that writes custom
fields replaced by invenio-pidbox's CitationsComponent. The stock component
replaces all custom fields with what an update sends, and the deposit form
never sends `pidbox:citations`, so every edit of a record would delete its
citations until the next "Refresh citations" run."""


# Invenio-Pidbox
# ==============

PIDBOX_RECORD_RELATIONS = True
"""The store (PIDBOX_SQLITE_PATH, default /var/lib/commonmeta/commonmeta.sqlite3,
mounted from the host) answers for the vocabularies the Starter doesn't
import: a record commit accepts any organization the store's ROR holds, as
an affiliation or a funder, and any grant the store holds (Crossref grants,
DataCite Awards) as an award (invenio-pidbox 0.6.1+). The vocabularies still
count where they have entries, so the accepted set is the union of the two."""

PIDBOX_FRONTPAGE_METRICS = False
"""No metrics on the front page: its header band holds the About page's text,
and the Starter Packs follow (templates/semantic-ui/invenio_app_rdm/
frontpage.html)."""

PIDBOX_FRONTPAGE_METRICS_BACKGROUND = "#cbd5e1"
"""The light slate of the front page's header band and of the Starter Packs
below it, one band under the menubar: the navbar's grey, which the band
would take otherwise, is too dark for the About text's dark slate. It is
invenio-pidbox's setting for the metrics' band, which the Starter keeps
without the metrics (invenio_rdm_starter/header_frontpage.html)."""

PIDBOX_JOBS_COMMUNITY_TYPES = [
    "journal",
    "blog",
    "repository",
    "organization",
    "funder",
]
"""invenio-pidbox's jobs (Administration > Jobs) offer the communities of the
Starter Packs' types in a Community select: the works imports (Import a work,
Import works by ROR ID, by ORCID iD, by container) add their works to that
pack's community, and Refresh citations, Attach PDFs and Attach software
archives take only its records (invenio-pidbox, the release after 0.7.11).
The types are invenio_rdm_starter.starter_packs' PACK_TYPES."""
