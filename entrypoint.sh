#!/bin/bash
# Entrypoint script for Invenio RDM Starter
set -e

# Check if database setup has already been completed
if ! invenio db check 2>/dev/null; then

  # Creating database...
  invenio db init create

  # Creating files location...
  if [ -n "${INVENIO_S3_BUCKET_NAME}" ]; then
    invenio files location create --default s3-default  "s3://${INVENIO_S3_BUCKET_NAME}"
  else
    invenio files location create --default default  "file:///opt/invenio/var/instance/data"
  fi

  # Superuser role
  invenio roles create admin
  invenio access allow superuser-access role admin

  # Administration access role
  invenio roles create administration
  invenio access allow administration-access role administration

  # Administration moderation role
  invenio roles create administration-moderation
  invenio access allow administration-moderation role administration-moderation

  # Creating admin user if credentials are provided...
  if [ -n "${INVENIO_ADMIN_EMAIL}" ] && [ -n "${INVENIO_ADMIN_PASSWORD}" ]; then
    invenio users create "${INVENIO_ADMIN_EMAIL}" --password "${INVENIO_ADMIN_PASSWORD}" --active --confirm
    invenio roles add "${INVENIO_ADMIN_EMAIL}" admin
  fi
  
  # Dropping and re-reating indices...
  invenio index destroy --force --yes-i-know
  invenio index init

  echo "Database and search setup completed."
fi

if ! invenio rdm-records custom-fields exists -f "journal:journal" 2>/dev/null | grep -q "Field journal:journal exists"; then
  # Creating custom fields for records...
  invenio rdm-records custom-fields init

  # Creating custom fields for communities...
  invenio communities custom-fields init

  # Creating rdm fixtures...
  invenio rdm-records fixtures

  # Rebuilding all indices...
  invenio rdm rebuild-all-indices

  # Creating demo records and communities if enabled...
  if [ "${INVENIO_DEMO_DATA}" = "True" ]; then
    invenio rdm-records demo records --user "${INVENIO_ADMIN_EMAIL}"
    invenio rdm-records demo communities --user "${INVENIO_ADMIN_EMAIL}"
    echo "Demo data creation completed."
  fi

  # Declaring queues...
  invenio queues declare

  echo "Custom fields and fixtures setup completed."
fi

# Execute the main command (passed as arguments to this script)
exec "$@"
