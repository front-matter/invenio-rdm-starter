#!/bin/bash

echo "-- Setup InvenioRDM --"

# Creating database...
invenio db init create

# Creating files location...
invenio files location create --default s3-default  "s3://${INVENIO_S3_BUCKET_NAME}"

# Creating admin role...
invenio roles create admin

# Assigning superuser access to admin role...
invenio access allow superuser-access role admin

# Dropping and re-reating indices...
invenio index destroy --force --yes-i-know
invenio index init

# Creating custom fields for records...
invenio rdm-records custom-fields init

# Creating custom fields for communities...
invenio communities custom-fields init

# Creating rdm fixtures...
invenio rdm-records fixtures

# Creating demo records...
# invenio rdm-records demo records --user user@demo.org

# Creating demo communities
# invenio rdm-records demo communities --user community@demo.org

# Declaring queues...
invenio queues declare

echo "-- Setup completed --"
