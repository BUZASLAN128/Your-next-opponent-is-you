ARG POSTGRES_BASE=postgres:18.4-bookworm@sha256:1961f96e6029a02c3812d7cb329a3b03a3ac2bb067058dec17b0f5596aca9296
FROM ${POSTGRES_BASE}

ARG PGVECTOR_VERSION=0.8.2
ARG PGVECTOR_COMMIT=cab9da72c04353f143bb06b42ab70a403daac64a
ARG PGVECTOR_SHA256=0af705b6c9b2a3a1fd1f6fd991425c125387d3c8edc68b75ef027d2e0a05e57a

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        postgresql-server-dev-18; \
    curl -fsSLo /tmp/pgvector.tar.gz \
        "https://github.com/pgvector/pgvector/archive/${PGVECTOR_COMMIT}.tar.gz"; \
    echo "${PGVECTOR_SHA256}  /tmp/pgvector.tar.gz" | sha256sum -c -; \
    mkdir /tmp/pgvector; \
    tar -xzf /tmp/pgvector.tar.gz --strip-components=1 -C /tmp/pgvector; \
    test "$(sed -n 's/^default_version = '\''\([^'\'']*\)'\''/\1/p' \
        /tmp/pgvector/vector.control)" = "${PGVECTOR_VERSION}"; \
    make -C /tmp/pgvector; \
    make -C /tmp/pgvector install; \
    rm -rf /tmp/pgvector /tmp/pgvector.tar.gz; \
    apt-get purge -y --auto-remove build-essential postgresql-server-dev-18 curl; \
    rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="YNOY PostgreSQL"
LABEL org.opencontainers.image.version="18.4-pgvector0.8.2"
LABEL org.opencontainers.image.source="https://github.com/BUZASLAN128/Your-next-opponent-is-you"
