![GitHub](https://img.shields.io/github/license/front-matter/invenio-rdm-starter?logo=MIT)

# InvenioRDM Starter

## Initial setup

```bash
# log into the invenio-rdm-starter container
docker exec -it invenio-rdm-starter-web-1  bash

# create the database and run migrations
invenio db create
invenio alembic upgrade

# (optional) load demo data
invenio rdm-records demo
invenio rdm-records fixtures

# create a user using (your) email address, you will be prompted for a password
invenio users create info@example.org  --active --confirm

# add the user to the admin role
invenio roles add info@example.org admin
```

You can now access the instance at https://localhost and login with the user you created. 
You may want to add a username and other details via the web interface.