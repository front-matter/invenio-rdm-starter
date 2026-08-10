FROM python:3.14-trixie AS builder

LABEL maintainer="Front Matter <info@front-matter.de>"
LABEL org.opencontainers.image.source="https://codeberg.org/front-matter/invenio-rdm-starter"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.title="InvenioRDM Starter"
LABEL org.opencontainers.image.description="InvenioRDM Starter is a turn-key research data management repository based on the InvenioRDM software."

ENV LANG=en_US.UTF-8 \
  LANGUAGE=en_US:en \
  VIRTUAL_ENV=/opt/invenio/.venv \
  UV_PROJECT_ENVIRONMENT=/opt/invenio/.venv \
  PATH="/opt/invenio/.venv/bin:$PATH" \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_PYTHON_DOWNLOADS=0 \
  INVENIO_INSTANCE_PATH=/opt/invenio/var/instance \
  WEBPACKEXT_PROJECT=invenio_assets.webpack:rspack_project

# Install OS package dependencies and Node.js in a single layer
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
  apt-get update --fix-missing && \
  curl -fsSL https://deb.nodesource.com/setup_24.x | bash - && \
  apt-get install -y build-essential python3-dev cargo pkg-config \
  libgdk-pixbuf-xlib-2.0-dev nodejs --no-install-recommends && \
  npm install -g pnpm@latest-10

# Install uv and activate virtualenv
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/
RUN uv venv /opt/invenio/.venv

WORKDIR /opt/invenio

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . .

# Install Python dependencies (use --no-editable so the project is installed as
# a proper wheel
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev --no-editable

# Build Javascript assets using rspack
RUN --mount=type=cache,target=/var/cache/assets \
  invenio collect --verbose && \
  invenio webpack create

# Copy application files to instance path
COPY ./invenio.cfg ${INVENIO_INSTANCE_PATH}/
COPY site ${INVENIO_INSTANCE_PATH}/site
COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
COPY templates ${INVENIO_INSTANCE_PATH}/templates
COPY app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY translations ${INVENIO_INSTANCE_PATH}/translations

# Compile assets using pnpm and rspack
WORKDIR ${INVENIO_INSTANCE_PATH}/assets
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
  pnpm install && \
  find node_modules -name tsconfig.json -not -path '*/@tsconfig/*' -delete && \
  pnpm run build

FROM python:3.14-slim-trixie AS runtime

# PATH carries the scripts directory so maintenance scripts run by bare name
# from any working directory.
ENV LANG=en_US.UTF-8 \
  LANGUAGE=en_US:en \
  VIRTUAL_ENV=/opt/invenio/.venv \
  PYTHONUNBUFFERED=1 \
  INVENIO_INSTANCE_PATH=/opt/invenio/var/instance \
  PATH="/opt/invenio/.venv/bin:/opt/invenio/var/instance/scripts:$PATH"

# create non-root invenio user
RUN adduser invenio --uid 1000 --gid 0 --no-create-home --disabled-password

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
  apt-get update --fix-missing && \
  apt-get install -y apt-utils gpg libcairo2 debian-keyring \
  debian-archive-keyring apt-transport-https curl --no-install-recommends && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy virtual environment and compiled files from builder stage
COPY --from=builder --chown=1000:0 ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --from=builder --chown=1000:0 ${INVENIO_INSTANCE_PATH}/assets ${INVENIO_INSTANCE_PATH}/assets
COPY --from=builder --chown=1000:0 ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder --chown=1000:0 ${INVENIO_INSTANCE_PATH}/translations ${INVENIO_INSTANCE_PATH}/translations

# Copy files needed at runtime
COPY --chown=1000:0 app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY --chown=1000:0 site ${INVENIO_INSTANCE_PATH}/site
COPY --chown=1000:0 templates ${INVENIO_INSTANCE_PATH}/templates
COPY --chown=1000:0 ./invenio.cfg ${INVENIO_INSTANCE_PATH}/invenio.cfg

# Prepare Gunicorn and Metrics
COPY --chown=1000:0 ./gunicorn.conf.py ${INVENIO_INSTANCE_PATH}/
RUN mkdir -p /tmp/prometheus_multiproc && chown 1000:0 /tmp/prometheus_multiproc

# Copy scripts used at runtime
COPY --chown=1000:0 --chmod=755 ./scripts ${INVENIO_INSTANCE_PATH}/scripts/

# Copy entrypoint script and set permissions
COPY --chown=1000:0 --chmod=755 ./entrypoint.sh /opt/invenio/.venv/bin/entrypoint.sh

WORKDIR /opt/invenio/src
USER invenio
EXPOSE 5000
CMD ["gunicorn", "invenio_app.wsgi:application", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--config", "/opt/invenio/var/instance/gunicorn.conf.py"]
