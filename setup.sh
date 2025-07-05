#!/bin/bash

echo "-- Setup InvenioRDM --"

# Creating database...
invenio db init create

# Creating files location...
invenio files location create --default default  "file://${INVENIO_DATADIR}"

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

# rebuilding all indices...
invenio rdm rebuild-all-indices

# Declaring queues...
invenio queues declare

echo "-- Setup completed --"
