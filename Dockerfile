# Dockerfile that builds the InvenioRDM Starter Docker image.
# Based on https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0
ARG BUILDPLATFORM=linux/amd64
FROM --platform=$BUILDPLATFORM python:3.12-bookworm AS builder

ENV POETRY_VERSION=1.8.2

# Install Node.js v18
RUN apt-get update && apt-get install -y curl=7.88.1-10+deb12u5 && \
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nsolid

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

ENV VIRTUAL_ENV=/opt/invenio/.venv \
    PATH="/opt/invenio/.venv/bin:$PATH" \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY ./site ./site
COPY ./templates ${INVENIO_INSTANCE_PATH}/templates
COPY ./app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY ./translations ${INVENIO_INSTANCE_PATH}/translations
COPY --from=builder ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder ${INVENIO_INSTANCE_PATH}/assets ${INVENIO_INSTANCE_PATH}/assets

# Create user
ENV INVENIO_USER_ID=1000
RUN adduser invenio --uid ${INVENIO_USER_ID} --gid 0

# Set folder permissions
# RUN chgrp -R 0 ${WORKDIR} && \
#     chmod -R g=u ${WORKDIR} && \
#     chown -R invenio:root ${WORKDIR}

USER invenio
EXPOSE 8080
CMD ["gunicorn", "-b",  "0.0.0.0:8080", "invenio_app.wsgi"]
