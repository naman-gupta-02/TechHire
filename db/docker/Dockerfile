# postgres:15-alpine + pgvector, compiled from source.
#
# Why not the official pgvector/pgvector image? It's Debian (glibc); the
# existing data volume was initialized by Alpine (musl). Text collation
# differs between the two C libraries, so reusing the volume across that
# switch can silently corrupt text indexes. Building pgvector into the
# same base image keeps the data volume fully compatible.
FROM postgres:15-alpine

ARG PGVECTOR_VERSION=v0.8.0

RUN apk add --no-cache --virtual .build-deps git build-base \
    && git clone --branch ${PGVECTOR_VERSION} --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
    && cd /tmp/pgvector \
    # with_llvm=no: the base image was built with LLVM JIT support, which
    # would otherwise make PGXS try to emit bitcode with a clang we don't
    # need. OPTFLAGS="" avoids -march=native so the image is portable.
    && make with_llvm=no OPTFLAGS="" \
    && make with_llvm=no install \
    && cd / && rm -rf /tmp/pgvector \
    && apk del .build-deps
