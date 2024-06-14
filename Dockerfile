FROM python:3.12 AS builder

# Dockerfile that builds the InvenioRDM Starter Docker image. Based on the following:
# - https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0
# - https://pythonspeed.com/articles/smaller-python-docker-images/
# - https://pythonspeed.com/articles/multi-stage-docker-python/

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    RYE_VERSION=0.34.0 \
    RYE_TOOLCHAIN=cpython@3.12 \
    UV_VERSION=0.2.9 \
    NODENV_VERSION=20.14.0 \
    VIRTUAL_ENV=/opt/invenio/.venv

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    apt-get update --fix-missing && apt-get install -y build-essential libssl-dev libffi-dev \
    python3-dev cargo pkg-config curl --no-install-recommends

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && apt-get clean

RUN python3 -m venv ${VIRTUAL_ENV}
# Make sure we use the virtualenv:
ENV PATH="${VIRTUAL_ENV}/bin:$PATH"

ENV WORKING_DIR=/opt/invenio \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

WORKDIR ${INVENIO_INSTANCE_PATH}

COPY pyproject.toml requirements.lock ./
RUN --mount=type=cache,target=/var/cache/pip pip install --no-cache-dir -r requirements.lock

COPY site ./site
COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
COPY templates ${INVENIO_INSTANCE_PATH}/templates
COPY app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY translations ${INVENIO_INSTANCE_PATH}/translations
COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}

# Build Javascript assets
RUN invenio collect --verbose && invenio webpack buildall

FROM python:3.12-slim-bookworm AS runtime

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt apt-get update -y --fix-missing && \
    apt-get install apt-utils libcairo2 curl -y --no-install-recommends && apt-get clean

ENV VIRTUAL_ENV=/opt/invenio/.venv \
    PATH="/opt/invenio/.venv/bin:$PATH" \
    WORKING_DIR=/opt/invenio \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --from=builder ${INVENIO_INSTANCE_PATH}/app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY --from=builder ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder ${INVENIO_INSTANCE_PATH}/translations ${INVENIO_INSTANCE_PATH}/translations
COPY --from=builder ${INVENIO_INSTANCE_PATH}/templates ${INVENIO_INSTANCE_PATH}/templates
COPY ./init.sh /opt/invenio/.venv/bin/init.sh

WORKDIR ${WORKING_DIR}/src

# Create invenio user and set appropriate permissions
ENV INVENIO_USER_ID=1000
RUN adduser invenio --uid ${INVENIO_USER_ID} --gid 0 --no-create-home --disabled-password && \
    chown -R invenio:root /opt/invenio/src && \
    chown -R invenio:root /opt/invenio/var
# USER invenio

EXPOSE 5000
CMD ["gunicorn", "invenio_app.wsgi:application", "--bind", "0.0.0.0:5000", "--workers", "4"]
