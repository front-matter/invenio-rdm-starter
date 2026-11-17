"""InvenioRDM Starter permissions.

These permissions are restrictive and only allow admin users to manage records."""

from invenio_access import action_factory
from invenio_communities.permissions import CommunityPermissionPolicy
from invenio_rdm_records.services.generators import AccessGrant, RecordOwners
from invenio_rdm_records.services.permissions import RDMRecordPermissionPolicy
from invenio_records.dictutils import dict_lookup
from invenio_records_permissions.generators import (
    ConditionalGenerator,
    Generator,
    SystemProcess,
)

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
