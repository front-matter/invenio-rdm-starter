#!/bin/bash

CONTAINER_ALREADY_STARTED="CONTAINER_ALREADY_STARTED"
if [ ! -e $CONTAINER_ALREADY_STARTED ]; then
    echo "-- First container startup --"
    
    # create the database and run migrations
    invenio db create
    invenio alembic upgrade

    # create the default location for InvenioRDM files
    invenio files location create --default default-location /opt/invenio/var/instance/data
    invenio communities custom-fields init
    invenio rdm-records custom-fields init
    
    # drop and re-create the OpenSearch indexes
    invenio index destroy --force --yes-i-know
    invenio index init
    invenio queues declare

    # load vocabularies
    invenio rdm-records fixtures

    # load demo data
    invenio rdm-records demo

    # add admin role
    invenio roles create admin
    invenio access allow superuser-access role admin
    touch $CONTAINER_ALREADY_STARTED
    echo "-- First container startup completed --"
else
    echo "-- Not first container startup --"
fi
gunicorn invenio_app.wsgi:application --bind 0.0.0.0:5000 --workers=4 