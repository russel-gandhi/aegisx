# infra/qdrant/Dockerfile
#
# Thin derived image whose only purpose is to give the Qdrant container an
# HTTP client for its own Compose healthcheck. No vendor-published Qdrant
# tag ships curl, wget, or netcat (verified against the vendor's own
# Dockerfile in RESEARCH.md — the runtime stage is `debian:13-slim` with
# only ca-certificates/tzdata/libunwind8 added). This is a build-time-only
# addition; it changes no runtime behavior of the Qdrant binary itself.
#
# Runtime user: `docker image inspect qdrant/qdrant:v1.19.0 --format
# '{{.Config.User}}'` reported `0:0` at build time — the vendor image
# already runs as root. USER root here is a no-op relative to the vendor
# image, and the final USER line restores that exact captured value so
# this derived image introduces no privilege delta.
FROM qdrant/qdrant:v1.19.0
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
USER 0:0
