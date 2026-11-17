FROM python:3.14-trixie AS builder

LABEL maintainer="Front Matter <info@front-matter.de>"
LABEL org.opencontainers.image.source="https://github.com/front-matter/invenio-rdm-starter"
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
    INVENIO_WEBPACKEXT_PROJECT=invenio_assets.webpack:rspack_project

# The INVENIO_ prefix is load-bearing: invenio-config only copies environment
# variables into the Flask config when they carry it, so an unprefixed
# WEBPACKEXT_PROJECT is silently ignored and the build runs webpack and terser
# instead of rspack.

# Install OS package dependencies
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    apt-get update --fix-missing && \
    apt-get install -y build-essential python3-dev cargo pkg-config \
    libgdk-pixbuf-xlib-2.0-dev --no-install-recommends

# npm is a node script rather than a binary, so it needs its lib directory and
# the shims the image keeps in /usr/local/bin as relative symlinks.
#
# pnpm is pinned exactly rather than tracking `latest-10`: a pnpm minor release
# can change how the lockfile resolves, so a floating tag means two builds of
# the same commit can ship different JavaScript. Bump deliberately.
COPY --from=node:26-trixie-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:26-trixie-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    npm install -g pnpm@10.34.5

# Install uv and activate virtualenv
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/
RUN uv venv /opt/invenio/.venv

WORKDIR /opt/invenio

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy the wheel's own inputs, and only those: hatch packages
# site/invenio_rdm_starter/*.py, and `readme = "README.md"` makes the README part of
# the project metadata. `COPY . .` here instead would put every template,
# config file and script ahead of the asset build below, so editing one line of
# a template would rebuild all the JavaScript.
COPY README.md ./
COPY site ./site

# Install Python dependencies (use --no-editable so the project is installed as
# a proper wheel
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# Build Javascript assets using rspack. The instance assets directory and its
# package.json are generated here from the installed packages' webpack entry
# points; the repo's own package.json and pnpm-lock.yaml are for local work and
# are not read by this build.
RUN invenio collect --verbose && \
    invenio webpack create

# Copy the application files this stage actually needs: assets is what rspack
# bundles, and static and translations are pulled back out with --from=builder
# by the runtime stage. invenio.cfg, site, templates and app_data used to be
# copied here as well, but no build step reads them and the runtime stage takes
# its own copies straight from the build context.
COPY static ${INVENIO_INSTANCE_PATH}/static
COPY assets ${INVENIO_INSTANCE_PATH}/assets
COPY translations ${INVENIO_INSTANCE_PATH}/translations

# Compile assets using pnpm and rspack
WORKDIR ${INVENIO_INSTANCE_PATH}/assets
# Many monorepo-published deps (@uppy, @react-dnd, @transloadit, …) ship a
# tsconfig.json whose `extends` points at a shared config (tsconfig.shared /
# tsconfig.base) that is not included in the npm tarball. rspack reads the
# nearest tsconfig when processing a module and follows its `extends`, so it
# fails to resolve the missing file and aborts the build. These are dev-build
# configs — the packages ship precompiled dist/lib, so they are unused for
# bundling. Strip every dependency tsconfig.json so rspack can't follow a broken
# reference; keep @tsconfig/* (genuine published base configs others extend).
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install && \
    find node_modules -name tsconfig.json -not -path '*/@tsconfig/*' -delete && \
    pnpm run build

FROM python:3.14-slim-trixie AS runtime

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    VIRTUAL_ENV=/opt/invenio/.venv \
    PYTHONUNBUFFERED=1 \
    INVENIO_INSTANCE_PATH=/opt/invenio/var/instance \
    PATH="/opt/invenio/.venv/bin:$PATH"

# create non-root invenio user
RUN adduser invenio --uid 1000 --gid 0 --no-create-home --disabled-password

# Install OS package dependencies: the shared libraries of WeasyPrint and
# cairosvg, loaded through cffi at import time. cairosvg comes with
# invenio-app-rdm and needs libcairo2; WeasyPrint comes with commonmeta-py
# (through invenio-rdm-records and invenio-pidbox), which renders PDFs with it.
# Without them `import weasyprint` raises
#
#     OSError: cannot load library 'libgobject-2.0-0'
#
# and every rendition fails. libgobject arrives as a dependency of pango rather
# than by name. fonts-dejavu-core is not optional either: the import succeeds
# without any font installed, and then pages render with no usable typeface.
RUN --mount=type=cache,sharing=locked,target=/var/cache/apt \
    apt-get update --fix-missing && \
    apt-get install -y libcairo2 libpango-1.0-0 libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 fonts-dejavu-core --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy virtual environment and compiled files from builder stage.
#
# The assets directory is deliberately not among them. It is where pnpm and
# rspack work, so copying it brings its node_modules along -- over 700 MB of
# the image, in a single layer. Nothing reads it at runtime: gunicorn serves
# what rspack already wrote to static/dist, whose manifest.json is how
# Flask-WebpackExt finds a bundle, and the entrypoint runs no webpack or
# collect step. The cost is that assets cannot be rebuilt inside a running
# container; `invenio webpack` belongs to the build.
COPY --from=builder --chown=1000:0 ${VIRTUAL_ENV} ${VIRTUAL_ENV}
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

# Copy entrypoint script and set permissions
COPY --chown=1000:0 --chmod=755 ./entrypoint.sh /opt/invenio/.venv/bin/entrypoint.sh

# The instance path, not /opt/invenio/src: nothing creates that directory, so
# the WORKDIR instruction made it — owned by root, while the process runs as
# uid 1000. It was an empty cwd nothing could write to. The instance path is
# owned by the invenio user.
WORKDIR ${INVENIO_INSTANCE_PATH}
USER invenio
EXPOSE 5000
CMD ["gunicorn", "invenio_app.wsgi:application", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--config", "/opt/invenio/var/instance/gunicorn.conf.py"]
