FROM debian:bookworm-slim AS unpack
RUN apt-get update && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/*
ARG TARGETARCH
ARG XRAYR_VERSION=v0.9.5
COPY dist/${XRAYR_VERSION}/ /archives/
RUN set -eu; \
    case "$TARGETARCH" in amd64) arch=64 ;; arm64) arch=arm64-v8a ;; s390x) arch=s390x ;; *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; esac; \
    cd /archives; \
    asset="XrayR-linux-${arch}.zip"; \
    awk -v name="$asset" '$2 == name {print}' SHA256SUMS > selected.sha256; \
    test "$(wc -l < selected.sha256)" -eq 1; \
    sha256sum -c selected.sha256; \
    unzip "$asset" -d /out; \
    chmod 755 /out/XrayR

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*
LABEL org.opencontainers.image.source="https://github.com/okoklai/XrayR1"
WORKDIR /etc/XrayR
COPY --from=unpack /out/XrayR /usr/local/bin/XrayR
COPY config/ /etc/XrayR/
COPY LICENSE /usr/share/licenses/XrayR/LICENSE
ENTRYPOINT ["XrayR", "--config", "/etc/XrayR/config.yml"]
