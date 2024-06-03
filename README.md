![GitHub](https://img.shields.io/github/license/front-matter/invenio-rdm-starter?logo=MIT)

# InvenioRDM Starter

## Initial setup

```bash
# log into the invenio-rdm-starter container
docker exec -it invenio-rdm-starter-web-1 bash

# create the database and run migrations
invenio db create
invenio alembic upgrade
invenio index init
invenio files location create --default default-location /opt/invenio/var/instance/data
invenio communities custom-fields init
invenio rdm-records custom-fields init
invenio queues declare

# load vocabularies
invenio rdm-records fixtures

# (optional) load demo data
invenio rdm-records demo

# create a user using (your) email address, you will be prompted for a password
invenio users create info@example.org  --active --confirm

# add the user to the admin role
invenio roles add info@example.org admin
invenio access allow superuser-access role admin
```

You can now access the instance at https://localhost and login with the user you created. 
You may want to add a username and other details via the web interface.

# Cleaning up the instance

```bash
# log into the invenio-rdm-starter container
docker exec -it invenio-rdm-starter-web-1  bash

# drop the database
invenio db drop --yes-i-know

# remove the opensearch indexes
invenio index destroy

# remove the files location
invenio files location delete default-location