# Dockerfile that builds the InvenioRDM Starter Docker image.
# Based on https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0

# syntax=docker/dockerfile:1.5
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

ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

WORKDIR /opt/invenio
ENV WORKING_DIR=/opt/invenio
ENV INVENIO_INSTANCE_PATH=${WORKING_DIR}/var/instance

COPY pyproject.toml poetry.lock ./
RUN touch README.md
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --without dev --no-root --no-interaction --no-ansi

COPY site ./site
COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
COPY templates ${INVENIO_INSTANCE_PATH}/templates
COPY app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY translations ${INVENIO_INSTANCE_PATH}/translations

RUN poetry run invenio collect --verbose && \
    poetry run invenio webpack buildall

FROM python:3.12-slim-bookworm AS runtime

# Install OS package dependency
RUN --mount=type=cache,target=/var/cache/apt apt-get update -y && \
    apt-get install libcairo2 libxmlsec1 -y --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/invenio

ENV VIRTUAL_ENV=/opt/invenio/.venv \
    PATH="/opt/invenio/.venv/bin:$PATH" \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

WORKDIR ${WORKING_DIR}/src

# RUN mkdir ${INVENIO_INSTANCE_PATH}/data && \
#     mkdir ${INVENIO_INSTANCE_PATH}/archive


COPY --from=builder ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder ${INVENIO_INSTANCE_PATH}/assets ${INVENIO_INSTANCE_PATH}/assets

# Create user and set permissions
ENV INVENIO_USER_ID=1000
# RUN adduser invenio --uid ${INVENIO_USER_ID} --gid 0 --no-create-home && \
#     chgrp -R +0 ${WORKDIR}
#     # chmod -R g=u ${WORKDIR} && \
#     # chown -R invenio:root ${WORKDIR}

# USER invenio
EXPOSE 5000
CMD ["gunicorn", "invenio_app.wsgi", "--bind", "0.0.0.0:5000", "--workers", "4"]
