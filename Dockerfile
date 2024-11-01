FROM python:3.12-bookworm AS builder

# Dockerfile that builds the InvenioRDM Starter Docker image. Based on the following:
# - https://medium.com/@albertazzir/blazing-fast-python-docker-builds-with-poetry-a78a66f5aed0
# - https://pythonspeed.com/articles/smaller-python-docker-images/
# - https://pythonspeed.com/articles/multi-stage-docker-python/

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    apt-get update --fix-missing && apt-get install -y build-essential libssl-dev libffi-dev \
    python3-dev cargo pkg-config curl --no-install-recommends

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && apt-get clean

# Install uv and activate virtualenv
COPY --from=ghcr.io/astral-sh/uv:0.4.15 /uv /bin/uv
RUN uv venv /opt/invenio/.venv
# Use the virtual environment automatically
ENV VIRTUAL_ENV=/opt/invenio/.venv \
    # Place entry points in the environment at the front of the path
    PATH="/opt/invenio/.venv/bin:$PATH" \
    WORKING_DIR=/opt/invenio \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

WORKDIR ${INVENIO_INSTANCE_PATH}

COPY pyproject.toml requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt
COPY . .

COPY site ${INVENIO_INSTANCE_PATH}/site
COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
COPY templates ${INVENIO_INSTANCE_PATH}/templates
COPY app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY translations ${INVENIO_INSTANCE_PATH}/translations
COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}

# Build Javascript assets
RUN --mount=type=cache,target=/var/cache/assets uv run invenio collect --verbose && uv run invenio webpack buildall

FROM python:3.12-slim-bookworm AS runtime

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt apt-get update -y --fix-missing && \
    apt-get install apt-utils gpg libcairo2 debian-keyring debian-archive-keyring apt-transport-https curl -y --no-install-recommends && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg && \
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list && \
    apt update && apt install caddy && apt-get clean 

ENV VIRTUAL_ENV=/opt/invenio/.venv \
    PATH="/opt/invenio/.venv/bin:$PATH" \
    WORKING_DIR=/opt/invenio \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --from=builder ${INVENIO_INSTANCE_PATH}/site ${INVENIO_INSTANCE_PATH}/site
COPY --from=builder ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder ${INVENIO_INSTANCE_PATH}/assets ${INVENIO_INSTANCE_PATH}/assets
COPY --from=builder ${INVENIO_INSTANCE_PATH}/templates ${INVENIO_INSTANCE_PATH}/templates
COPY --from=builder ${INVENIO_INSTANCE_PATH}/app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY --from=builder ${INVENIO_INSTANCE_PATH}/translations ${INVENIO_INSTANCE_PATH}/translations
COPY --from=builder ${INVENIO_INSTANCE_PATH}/invenio.cfg ${INVENIO_INSTANCE_PATH}/invenio.cfg
COPY ./Caddyfile /etc/caddy/Caddyfile

COPY ./setup.sh /opt/invenio/.venv/bin/setup.sh

WORKDIR ${WORKING_DIR}/src

# Create invenio user and set appropriate permissions
ENV INVENIO_USER_ID=1000
RUN adduser invenio --uid ${INVENIO_USER_ID} --gid 0 --no-create-home --disabled-password && \
    chown -R invenio:root /opt/invenio/src && \
    chown -R invenio:root /opt/invenio/var
# USER invenio

EXPOSE 5000
CMD ["gunicorn", "invenio_app.wsgi:application", "--bind", "0.0.0.0:5000", "--workers", "4"]
