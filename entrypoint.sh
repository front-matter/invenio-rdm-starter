#!/bin/bash
# Entrypoint script for InvenioRDM Starter
set -e

# Creating database and tables if they do not exist...
invenio db init create

# Creating files location...
invenio files location create --default s3-default  "s3://${S3_BUCKET}"

# Superuser role
invenio roles create admin
invenio access allow superuser-access role admin

# Administration access role
invenio roles create administration
invenio access allow administration-access role administration

# Administration moderation role
invenio roles create administration-moderation
invenio access allow administration-moderation role administration-moderation

# Creating indices if they do not exist...
invenio index init

# Creating custom fields for records...
invenio rdm-records custom-fields init

# Creating custom fields for communities...
invenio communities custom-fields init

# Creating rdm fixtures...
invenio rdm-records fixtures

# rebuilding all indices...
invenio rdm rebuild-all-indices

# Declaring queues...
invenio queues declare

exec "$@"
