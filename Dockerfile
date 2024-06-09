# syntax=docker/dockerfile:1.5
ARG BUILDPLATFORM=linux/amd64,linux/arm64
FROM python:3.12-bookworm AS builder

# Dockerfile that builds the InvenioRDM Starter Docker image. Based on the following:
# - https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0
# - https://pythonspeed.com/articles/smaller-python-docker-images/
# - https://pythonspeed.com/articles/multi-stage-docker-python/
# - https://stackoverflow.com/questions/53835198/integrating-python-poetry-with-docker

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8 \
    RYE_VERSION=0.34.0 \
    NODENV_VERSION=20.14.0

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    apt-get update --fix-missing && apt-get install -y build-essential libssl-dev libffi-dev \
    python3-dev cargo pkg-config curl --no-install-recommends

# Explicitly set the virtual environment used by Poetry
ENV WORKING_DIR=/opt/invenio
ENV VIRTUAL_ENV=/opt/invenio/.venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="/opt/invenio/.venv/bin:$PATH"

# Install Rye
RUN curl -sSf https://rye.astral.sh/get | bash

ENV INVENIO_INSTANCE_PATH=${WORKING_DIR}/var/instance

WORKDIR ${WORKING_DIR}

COPY pyproject.toml ./
RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-root --only main --no-interaction --no-ansi

# COPY site ./site
COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
COPY templates ${INVENIO_INSTANCE_PATH}/templates
COPY app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY translations ${INVENIO_INSTANCE_PATH}/translations
COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}

# Install Node.js into the virtual environment and build assets
RUN poetry run nodeenv -p --node=${NODENV_VERSION} --prebuilt && \
    invenio collect --verbose && poetry run invenio webpack buildall

FROM python:3.12-slim-bookworm AS runtime

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt apt-get update -y --fix-missing && \
    apt-get install apt-utils libcairo2 curl -y --no-install-recommends && apt-get clean

ENV VIRTUAL_ENV=/opt/invenio/.venv \
    PATH="/opt/invenio/.venv/bin:$PATH" \
    WORKING_DIR=/opt/invenio \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
# COPY --from=builder ${VIRTUAL_ENV}/lib ${VIRTUAL_ENV}/lib
# COPY --from=builder ${VIRTUAL_ENV}/bin ${VIRTUAL_ENV}/bin
# COPY --from=builder ${VIRTUAL_ENV}/include ${VIRTUAL_ENV}/include
COPY --from=builder ${INVENIO_INSTANCE_PATH}/app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY --from=builder ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder ${INVENIO_INSTANCE_PATH}/translations ${INVENIO_INSTANCE_PATH}/translations
COPY --from=builder ${INVENIO_INSTANCE_PATH}/templates ${INVENIO_INSTANCE_PATH}/templates

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
