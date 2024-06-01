# syntax=docker/dockerfile:1.5
ARG BUILDPLATFORM=linux/amd64
FROM --platform=$BUILDPLATFORM python:3.12-bookworm AS builder

# Dockerfile that builds the InvenioRDM Starter Docker image. Based on the following:
# - https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0
# - https://pythonspeed.com/articles/smaller-python-docker-images/
# - https://pythonspeed.com/articles/multi-stage-docker-python/
# - https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    POETRY_VERSION=1.8.3

# Install OS package dependencies
RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update --fix-missing && apt-get install -y build-essential libssl-dev libffi-dev \
    python3-dev cargo pkg-config --no-install-recommends

# Install Node.js v20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x -o nodesource_setup.sh && \
    bash nodesource_setup.sh && \
    apt-get install -y nodejs

# Explicitly set the virtual environment used by Poetry
ENV WORKING_DIR=/opt/invenio
ENV VIRTUAL_ENV=/opt/invenio/.venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="/opt/invenio/.venv/bin:$PATH"

# Install Poetry 
RUN pip install --upgrade --no-cache-dir "poetry==${POETRY_VERSION}" pip wheel

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=0 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

ENV INVENIO_INSTANCE_PATH=${WORKING_DIR}/var/instance

WORKDIR ${WORKING_DIR}

COPY pyproject.toml poetry.lock ./
RUN touch README.md
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-root --no-dev --no-interaction --no-ansi

COPY site ./site
COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
COPY templates ${INVENIO_INSTANCE_PATH}/templates
COPY app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY translations ${INVENIO_INSTANCE_PATH}/translations
COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}

RUN poetry run invenio collect --verbose && poetry run invenio webpack buildall

FROM python:3.12-slim-bookworm AS runtime

# Install OS package dependency
RUN --mount=type=cache,target=/var/cache/apt apt-get update -y --fix-missing && \
    apt-get install libcairo2 -y --no-install-recommends && \
    apt-get clean

ENV VIRTUAL_ENV=/opt/invenio/.venv \
    PATH="/opt/invenio/.venv/bin:$PATH" \
    WORKING_DIR=/opt/invenio \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY --from=builder ${WORKING_DIR} ${WORKING_DIR}

RUN pip install --upgrade --force-reinstall invenio-app-rdm==12.0.0rc2

WORKDIR ${WORKING_DIR}/src

# RUN mkdir ${INVENIO_INSTANCE_PATH}/data && \
#     mkdir ${INVENIO_INSTANCE_PATH}/archive

# Create user and set permissions
ENV INVENIO_USER_ID=1000
RUN adduser invenio --uid ${INVENIO_USER_ID} --gid 0 --no-create-home
#     chgrp -R +0 ${WORKDIR}
#     # chmod -R g=u ${WORKDIR} && \
#     # chown -R invenio:root ${WORKDIR}

# USER invenio
EXPOSE 5000
CMD ["gunicorn", "invenio_app.wsgi:application", "--bind", "0.0.0.0:5000", "--workers", "4"]
