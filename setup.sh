#!/bin/bash

SETUP_COMPLETED="SETUP_COMPLETED"
if [ ! -e $SETUP_COMPLETED ]; then
    echo "-- Setup InvenioRDM --"

    # Creating database...
    invenio db init create

    # Creating files location...
    invenio files location create --default default-location /opt/invenio/var/instance/data

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

    # Creating rdm fixtures if...
    invenio rdm-records fixtures

    # Creating demo records...
    invenio rdm-records demo

    # Declaring queues...
    invenio queues declare

    touch $SETUP_COMPLETED
    echo "-- Setup completed --"
else
    echo "-- No setup needed --"
fi

# Start application server
gunicorn invenio_app.wsgi:application --bind 0.0.0.0:5000 --workers=4
