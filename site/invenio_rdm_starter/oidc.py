"""OAuth logins on the invenio-oauthclient authlib branch.

OAuthClientRemoteApp logs in through any provider's OIDC: Keycloak,
Authentik, ORCID, Google and Discord. It replaces the branch's OIDCRemoteApp
mapping, which the signup form has no fields for and which trusts every email
address:

- The email address is used only if the email_verified claim is true. Without
  one the user types an address into the signup form and confirms it by email.
- Every account gets a username, usr_ and eight random Crockford
  base32 characters. Providers send their own usernames, if any, which are
  not expected to follow it and are not used; one that already does, from a
  Keycloak with the keycloak-invenio auto-username mapper, is kept.
- An ORCID iD, from an orcid claim or, for ORCID itself, the subject, is
  linked to the user as a UserIdentity with method "orcid".

The username, full name and ORCID iD are also filled in on every login, so
accounts registered without them are repaired the next time their owner logs
in.

GitHubRemoteApp logs in with GitHub's OAuth2, which has no OIDC.
"""

from __future__ import annotations

import os
import re
import secrets
from collections.abc import Mapping
from urllib.parse import urlencode

import requests
import structlog
from flask import session
from invenio_accounts.models import User, UserIdentity
from invenio_accounts.utils import validate_username
from invenio_oauthclient.data import ServerMetadata, UserInfo
from invenio_oauthclient.remote_apps import BaseRemoteApp, OIDCRemoteApp
from invenio_oauthclient.utils import _create_registrationform

ORCID_PREFIXES = ("https://orcid.org/", "http://orcid.org/")

# Usernames are usr_ and eight characters of the Crockford base32
# alphabet, as the keycloak-invenio auto-username mapper generates them.
USERNAME_ALPHABET = "0123456789abcdefghjkmnpqrstvwxyz"


def generate_username() -> str:
    """Return a new username, usr_xxxxxxxx."""
    return "usr_" + "".join(secrets.choice(USERNAME_ALPHABET) for _ in range(8))


# Provider names that are not just the remote app's name capitalized.
TITLES = {"github": "GitHub", "orcid": "ORCID"}


def default_title(name: str) -> str:
    """The login button title for a remote app: Keycloak for keycloak."""
    return TITLES.get(name, name.title())


def default_icon(name: str) -> str:
    """The login button icon for a remote app, static/images/<name>.svg."""
    return f"images/{name}.svg"


def client_credentials(
    name: str,
    environ: Mapping[str, str] | None = None,
    required: bool = False,
) -> tuple[str | None, str | None]:
    """Return a provider's client id and secret from the environment.

    Read from INVENIO_<NAME>_CLIENT_ID and INVENIO_<NAME>_CLIENT_SECRET,
    authlib's names for them. An empty variable counts as not set.

    With required, a missing id or secret raises KeyError naming the
    variable, rather than registering a provider that can't log anyone in.
    """
    env = os.environ if environ is None else environ
    prefix = f"INVENIO_{name.upper()}"
    credentials = []
    for key in ("CLIENT_ID", "CLIENT_SECRET"):
        value = env.get(f"{prefix}_{key}") or None
        if value is None and required:
            raise KeyError(f"{prefix}_{key}")
        credentials.append(value)
    return credentials[0], credentials[1]


def normalize_orcid(value: object) -> str | None:
    """Return the bare ORCID iD from an ORCID iD or ORCID URL."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    for prefix in ORCID_PREFIXES:
        value = value.removeprefix(prefix)
    return value or None


# A username as generate_username() makes them.
USERNAME_SCHEME = re.compile(rf"usr_[{USERNAME_ALPHABET}]{{8}}")


class OAuthClientRemoteApp(OIDCRemoteApp):
    """Log in through a provider's OIDC, shaped for the signup form.

    The provider is given by its issuer: the discovery document is read from
    <issuer>/.well-known/openid-configuration, and logout ends the provider's
    session too if the document has an end_session_endpoint (Keycloak and
    Authentik do; ORCID, Google and Discord do not). server_metadata and
    logout_url override them. The scope is "openid email profile" unless
    scope is given. The login button's title is the name
    capitalized (ORCID and GitHub as they spell themselves) and its icon
    static/images/<name>.svg, unless title or icon is given.

    Claims missing from the ID token are read from the userinfo endpoint:
    Discord's ID token carries little more than the subject. orcid_claim names
    the claim with the user's ORCID iD; for ORCID itself it is "sub", and the
    ORCID iD is also the external id.
    """

    # Only an address the provider verified is passed on: new users are
    # confirmed when they register with it.
    email_verified = True

    def __init__(
        self,
        *args,
        issuer: str | None = None,
        server_metadata: str | ServerMetadata | None = None,
        scope: list[str] | str = "openid email profile",
        orcid_claim: str = "orcid",
        **kwargs,
    ):
        """Set the provider's issuer and the claim that carries the ORCID iD."""
        if server_metadata is None:
            if not issuer:
                raise ValueError("an issuer or server_metadata is required")
            server_metadata = f"{issuer}/.well-known/openid-configuration"
        self.issuer = issuer
        self.orcid_claim = orcid_claim
        title = kwargs.pop("title", None)
        icon = kwargs.pop("icon", None)
        super().__init__(*args, server_metadata=server_metadata, scope=scope, **kwargs)
        self.title = title or default_title(self.name)
        self.icon = icon or default_icon(self.name)

    @property
    def logout_url(self) -> str | None:
        """Where logging out sends the user to end the provider's session.

        The configured logout_url, or else the end_session_endpoint of the
        discovery document, which authlib loads once and keeps.
        """
        if self._logout_url is not None:
            return self._logout_url
        if self.client is None:
            return None
        try:
            metadata = self.client.load_server_metadata()
        except (requests.RequestException, ValueError) as error:
            structlog.get_logger().bind(service="invenio-rdm-starter").warning(
                "oidc discovery failed", remote_app=self.name, error=str(error)
            )
            return None
        endpoint = metadata.get("end_session_endpoint")
        if not endpoint:
            return None
        separator = "&" if "?" in endpoint else "?"
        return f"{endpoint}{separator}{urlencode({'client_id': self.client_id})}"

    @logout_url.setter
    def logout_url(self, value: str | None) -> None:
        self._logout_url = value

    def parse_user_info(self, id_token: dict, extra_user_info: dict) -> UserInfo:
        """Shape the user info as the signup form's fields."""

        def claim(name: str):
            if name in id_token:
                return id_token[name]
            return extra_user_info.get(name)

        verified = claim("email_verified") in (True, "true")
        username = claim("preferred_username")
        if not (isinstance(username, str) and USERNAME_SCHEME.fullmatch(username)):
            username = generate_username()
        full_name = (
            claim("name")
            or claim("nickname")
            or " ".join(filter(None, (claim("given_name"), claim("family_name"))))
        )
        orcid = normalize_orcid(claim(self.orcid_claim))
        external_id = orcid if self.orcid_claim == "sub" else str(claim("sub"))
        return UserInfo(
            {
                "email": (claim("email") or "") if verified else "",
                "profile": {
                    "username": username,
                    "full_name": full_name or "",
                    "affiliations": claim("affiliation") or "",
                },
            },
            external_id,
            self.name,
            {"orcid": orcid} if orcid else {},
        )

    def finalize_login(self, user: User, user_info: UserInfo, *args, **kwargs) -> None:
        """Fill in what the account is missing, then finish the login."""
        log = structlog.get_logger().bind(
            service="invenio-rdm-starter", user_id=user.id
        )
        profile = user_info.user.get("profile", {})

        username = profile.get("username")
        if not user.username and username:
            if User.query.filter(User.username == username).one_or_none():
                log.warning("oidc username taken", username=username)
            else:
                user.username = username

        full_name = profile.get("full_name")
        if full_name and not (user.user_profile or {}).get("full_name"):
            user.user_profile = {
                **(user.user_profile or {}),
                "full_name": full_name,
            }

        orcid = user_info.extra_data.get("orcid")
        if orcid:
            owner = UserIdentity.get_user("orcid", orcid)
            if owner is None:
                UserIdentity.create(user, "orcid", orcid)
                log.info("orcid linked", orcid=orcid)
            elif owner.id != user.id:
                log.warning("orcid linked to another user", orcid=orcid)

        super().finalize_login(user, user_info, *args, **kwargs)


GITHUB_SERVER_METADATA = ServerMetadata(
    authorize_url="https://github.com/login/oauth/authorize",
    access_token_url="https://github.com/login/oauth/access_token",
    api_base_url="https://api.github.com/",
)


class GitHubRemoteApp(BaseRemoteApp):
    """Log in with a GitHub account through GitHub's OAuth2.

    GitHub has no OIDC: there is no ID token, so the user and their email
    addresses are read from the REST API. Only the primary address, and only
    if GitHub has verified it, is used; without one the user types an address
    into the signup form and confirms it by email.
    """

    email_verified = True

    def __init__(self, *args, **kwargs):
        """Configure GitHub's endpoints."""
        kwargs.setdefault("server_metadata", GITHUB_SERVER_METADATA)
        # The profile and the email addresses, read-only.
        kwargs.setdefault("scope", "read:user user:email")
        # GitHub documents the client secret in the token request body only.
        kwargs.setdefault(
            "client_kwargs",
            {"token_endpoint_auth_method": "client_secret_post"},
        )
        title = kwargs.pop("title", None)
        icon = kwargs.pop("icon", None)
        super().__init__(*args, **kwargs)
        self.title = title or default_title(self.name)
        self.icon = icon or default_icon(self.name)

    def get_more_user_info(self, access_token: str) -> dict:
        """Read the GitHub user and their email addresses."""
        token = {"access_token": access_token, "token_type": "bearer"}
        headers = {"Accept": "application/vnd.github+json"}
        user = self.client.get("user", token=token, headers=headers)
        user.raise_for_status()
        emails = self.client.get("user/emails", token=token, headers=headers)
        emails.raise_for_status()
        return {"user": user.json(), "emails": emails.json()}

    def parse_user_info(self, id_token: dict, extra_user_info: dict) -> UserInfo:
        """Shape the user info as the signup form's fields."""
        user = extra_user_info["user"]
        email = next(
            (
                e["email"]
                for e in extra_user_info["emails"]
                if e.get("primary") and e.get("verified")
            ),
            "",
        )
        return UserInfo(
            {
                "email": email,
                "profile": {
                    "username": generate_username(),
                    "full_name": user.get("name") or "",
                    "affiliations": "",
                },
            },
            str(user["id"]),
            self.name,
            {"login": user.get("login"), "id": user["id"]},
        )


def _provider_username(remote_app) -> str | None:
    """The username the remote app sent, kept in the session for the form."""
    if remote_app is None:
        return None
    info = session.get(f"{remote_app.name}_userinfo")
    username = getattr(info, "user", {}).get("profile", {}).get("username")
    try:
        validate_username(username or "")
    except ValueError:
        # A username Invenio rejects stays editable rather than leave the
        # user stuck. parse_user_info only sends usr_xxxxxxxx ones, but a
        # remote app that keeps the provider's own could send anything.
        return None
    return username


def signup_form(*args, **kwargs):
    """The signup form after an OAuth login, OAUTHCLIENT_SIGNUP_FORM.

    The branch's default form, with the email address marked as required (the
    server already rejects an empty one) and the username from the remote app
    read-only: every account has a usr_xxxxxxxx username. Read-only is only the browser's side, so the username
    the remote app sent is put back into the submitted form as well.
    """
    form = _create_registrationform(*args, **kwargs)
    form.email.render_kw = {**(form.email.render_kw or {}), "required": True}
    username = _provider_username(kwargs.get("oauth_remote_app"))
    if username:
        field = form.profile.username
        field.data = username
        field.render_kw = {**(field.render_kw or {}), "readonly": True}
    return form
