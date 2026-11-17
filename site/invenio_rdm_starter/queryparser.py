"""Query parser helpers of InvenioRDM Starter."""

from invenio_communities.communities.records.models import CommunityMetadata
from invenio_db import db
from luqum.tree import Phrase


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
