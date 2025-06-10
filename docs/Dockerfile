FROM squidfunk/mkdocs-material:9.6 AS builder
WORKDIR /app
COPY docs /app/docs
RUN ["docs/mkdocs", "build"]
