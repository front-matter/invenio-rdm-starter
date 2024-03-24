# Dockerfile that builds the InvenioRDM Starter Docker image.
# Based on https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0
ARG BUILDPLATFORM=linux/amd64
FROM --platform=$BUILDPLATFORM python:3.12-bookworm AS builder

ENV POETRY_VERSION=1.8.2

# Install Node.js v20
RUN --mount=type=cache,target=/var/cache/apt \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update && apt-get install -y nsolid apt-utils build-essential python3-dev cargo pkg-config --no-install-recommends

# Install Poetry 
RUN pip install --no-cache-dir poetry==${POETRY_VERSION} 

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /opt/invenio
COPY pyproject.toml poetry.lock ./
RUN touch README.md
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev --no-root

ENV INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
RUN poetry run invenio collect --verbose && \
    poetry run invenio webpack buildall


FROM python:3.12-slim-bookworm AS runtime

WORKDIR /opt/invenio

ENV VIRTUAL_ENV=/opt/invenio/.venv \
    PATH="/opt/invenio/.venv/bin:$PATH" \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

# RUN mkdir ${INVENIO_INSTANCE_PATH}/data && \
#     mkdir ${INVENIO_INSTANCE_PATH}/archive

COPY ./site ./site
COPY ./templates ${INVENIO_INSTANCE_PATH}/templates
COPY ./app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY ./translations ${INVENIO_INSTANCE_PATH}/translations
COPY --from=builder ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder ${INVENIO_INSTANCE_PATH}/assets ${INVENIO_INSTANCE_PATH}/assets

# Create user and set permissions
ENV INVENIO_USER_ID=1000
# RUN adduser invenio --uid ${INVENIO_USER_ID} --gid 0 --no-create-home && \
#     chgrp -R +0 ${WORKDIR}
#     # chmod -R g=u ${WORKDIR} && \
#     # chown -R invenio:root ${WORKDIR}

# For the full list of settings and their values, see
# https://inveniordm.docs.cern.ch/reference/configuration/
ENV INVENIO_ACCOUNTS_SESSION_REDIS_URL=redis://cache:6379/1 \
    INVENIO_BROKER_URL= \
    INVENIO_CACHE_REDIS_URL=redis://cache:6379/0 \
    INVENIO_CACHE_TYPE=redis \
    INVENIO_CELERY_BROKER_URL= \
    INVENIO_CELERY_RESULT_BACKEND=redis://cache:6379/2 \
    INVENIO_SEARCH_HOSTS=['search:9200'] \
    INVENIO_SECRET_KEY=CHANGE_ME \
    INVENIO_SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://invenio-rdm-starter:invenio-rdm-starter@db/invenio-rdm-starter \
    INVENIO_RATELIMIT_STORAGE_URL=redis://cache:6379/3

# USER invenio
EXPOSE 5000
CMD ["gunicorn", "invenio_app.wsgi:application", "--bind", "0.0.0.0:5000", "--workers", "4"]
