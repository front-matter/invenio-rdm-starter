"""The Content Security Policy lets the browser fetch the files from S3."""

from __future__ import annotations

import pytest
from invenio_rdm_starter import config


@pytest.mark.parametrize(
    ("endpoint", "sources"),
    [
        ("https://fsn1.your-objectstorage.com", ["fsn1.your-objectstorage.com"]),
        ("https://s3.example.org:9000/", ["s3.example.org:9000"]),
        ("", []),
        (None, []),
    ],
)
def test_the_s3_endpoints_host_is_a_source(endpoint, sources):
    assert config.s3_endpoint_sources(endpoint) == sources


def test_the_policy_keeps_the_amazon_hosts():
    default_src = config.APP_DEFAULT_SECURE_HEADERS["content_security_policy"][
        "default-src"
    ]

    assert "s3.eu-central-1.amazonaws.com" in default_src
    assert "'self'" in default_src
