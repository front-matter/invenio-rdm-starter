FROM dhi.io/python:3.13-debian13-dev AS builder
LABEL service="starter"
LABEL maintainer="Front Matter <info@front-matter.de>"

# Dockerfile that builds the InvenioRDM Starter Docker image using DHI
# (Docker Hardened Image) for enhanced security

ENV LANG=en_US.UTF-8 \
  LANGUAGE=en_US:en

# Install OS package dependencies and Node.js in a single layer
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
  apt-get update --fix-missing && \
  apt-get install -y build-essential libssl-dev libffi-dev \
  python3-dev cargo pkg-config curl libcairo2 \
  libpangocairo-1.0-0 libpq5 libxml2 libxslt1.1 \
  libjpeg62-turbo libwebp7 libtiff6 --no-install-recommends && \
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
  apt-get install -y nodejs --no-install-recommends && \
  npm install -g pnpm@latest-10

# Install uv and activate virtualenv
COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/
RUN uv venv /opt/invenio/.venv

# Use the virtual environment automatically
ENV VIRTUAL_ENV=/opt/invenio/.venv \
  UV_PROJECT_ENVIRONMENT=/opt/invenio/.venv \
  PATH="/opt/invenio/.venv/bin:$PATH" \
  WORKING_DIR=/opt/invenio \
  PYTHONDONTWRITEBYTECODE=1 \
  PYTHONUNBUFFERED=1 \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy \
  UV_PYTHON_DOWNLOADS=0 \
  INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

WORKDIR ${WORKING_DIR}

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . .

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-dev

# Build Javascript assets using rspack
ENV WEBPACKEXT_PROJECT=invenio_assets.webpack:rspack_project
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

# from: https://github.com/tu-graz-library/docker-invenio-base
# enables the option to have a deterministic javascript dependency build
# package.json and pnpm-lock are needed, because otherwise package.json
# is newer as pnpm-lock and pnpm-lock would not be used then
# do this only if you know what you are doing. forgetting to update those
# two files can cause bugs, because of possible missmatches of needed
# javascript dependencies
COPY ./package.json ${INVENIO_INSTANCE_PATH}/assets/
COPY ./pnpm-lock.yaml ${INVENIO_INSTANCE_PATH}/assets/

WORKDIR ${INVENIO_INSTANCE_PATH}/assets
RUN pnpm install && \
  pnpm run build

# Gather runtime libraries into a single directory for easy copying
RUN mkdir -p /invenio-libs && \
  cp -P /usr/lib/x86_64-linux-gnu/libcairo*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libpango*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libharfbuzz*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libfontconfig*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libfreetype*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libpixman*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libpng*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libexpat*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libxcb*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libX*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libfribidi*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libthai*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libglib*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libgobject*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libdatrie*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libpcre2*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libffi*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libbsd*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libmd*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libpq*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libssl*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libcrypto*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libxml2*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libxslt*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libexslt*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libjpeg*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libwebp*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libtiff*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libz*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/liblzma*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libcurl*.so* /invenio-libs/ && \
  cp -P /usr/lib/x86_64-linux-gnu/libnghttp*.so* /invenio-libs/ 2>/dev/null || true && \
  cp -P /usr/lib/x86_64-linux-gnu/librtmp*.so* /invenio-libs/ 2>/dev/null || true && \
  cp -P /usr/lib/x86_64-linux-gnu/libssh*.so* /invenio-libs/ 2>/dev/null || true && \
  cp -P /usr/lib/x86_64-linux-gnu/libicui18n*.so* /invenio-libs/ 2>/dev/null || true && \
  cp -P /usr/lib/x86_64-linux-gnu/libicuuc*.so* /invenio-libs/ 2>/dev/null || true && \
  cp -P /usr/lib/x86_64-linux-gnu/libicudata*.so* /invenio-libs/ 2>/dev/null || true

FROM dhi.io/python:3.13-debian13 AS runtime

ENV LANG=en_US.UTF-8 \
  LANGUAGE=en_US:en

# DHI images are minimal - copy required Cairo libraries from builder
# These are needed for cairosvg/cairocffi used by invenio_formatter

ENV VIRTUAL_ENV=/opt/invenio/.venv \
  PATH="/opt/invenio/.venv/bin:$PATH" \
  WORKING_DIR=/opt/invenio \
  INVENIO_INSTANCE_PATH=/opt/invenio/var/instance

# DHI uses UID 1654 as non-root user - already configured in base image
ENV INVENIO_USER_ID=1654

# DHI is shell-less by design for security
# entrypoint.py runs initialization in Python (no shell required)

# Copy runtime libraries from builder (Cairo for invenio_formatter, etc.)
COPY --from=builder /invenio-libs/* /usr/lib/x86_64-linux-gnu/

COPY --from=builder --chown=1654:0 ${VIRTUAL_ENV} ${VIRTUAL_ENV}
COPY --from=builder --chown=1654:0 ${INVENIO_INSTANCE_PATH}/site ${INVENIO_INSTANCE_PATH}/site
COPY --from=builder --chown=1654:0 ${INVENIO_INSTANCE_PATH}/static ${INVENIO_INSTANCE_PATH}/static
COPY --from=builder --chown=1654:0 ${INVENIO_INSTANCE_PATH}/assets ${INVENIO_INSTANCE_PATH}/assets
COPY --from=builder --chown=1654:0 ${INVENIO_INSTANCE_PATH}/templates ${INVENIO_INSTANCE_PATH}/templates
COPY --from=builder --chown=1654:0 ${INVENIO_INSTANCE_PATH}/app_data ${INVENIO_INSTANCE_PATH}/app_data
COPY --from=builder --chown=1654:0 ${INVENIO_INSTANCE_PATH}/translations ${INVENIO_INSTANCE_PATH}/translations
COPY --from=builder --chown=1654:0 ${INVENIO_INSTANCE_PATH}/invenio.cfg ${INVENIO_INSTANCE_PATH}/invenio.cfg
COPY --chown=1654:0 ./Caddyfile /etc/caddy/Caddyfile
COPY --chown=1654:0 --chmod=755 ./entrypoint.py ${INVENIO_INSTANCE_PATH}/entrypoint.py

# Declare volumes for persistent data (writable directories managed by DHI)
VOLUME ["/opt/invenio/var/instance/data", "/opt/invenio/var/instance/archive"]

WORKDIR ${WORKING_DIR}/src

EXPOSE 5000
ENTRYPOINT ["python3", "/opt/invenio/var/instance/entrypoint.py"]
CMD ["gunicorn", "invenio_app.wsgi:application", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "ERROR"]
