FROM mcr.microsoft.com/devcontainers/base:ubuntu-24.04

# TeX Live scheme-small plus the packages thesis/main.tex actually loads.
# Docs and sources are omitted so the Codespace image stays smaller.
USER root
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        fontconfig \
        libfile-homedir-perl \
        libfontconfig1 \
        libyaml-tiny-perl \
        perl \
        perl-modules \
        wget \
        xz-utils \
    && rm -rf /var/lib/apt/lists/*

# mirror.ctan.org redirects, and some mirrors present a certificate this image
# cannot verify. Try fixed mirrors that currently serve a complete tlnet.
RUN set -eu; \
    MIRROR=""; \
    for candidate in \
        https://mirror.ox.ac.uk/sites/ctan.org/systems/texlive/tlnet \
        https://ftp.jaist.ac.jp/pub/CTAN/systems/texlive/tlnet; \
    do \
        if wget -nv -O /tmp/install-tl-unx.tar.gz "$candidate/install-tl-unx.tar.gz"; then \
            MIRROR="$candidate"; \
            break; \
        fi; \
        rm -f /tmp/install-tl-unx.tar.gz; \
    done; \
    test -n "$MIRROR"; \
    mkdir -p /tmp/install-tl; \
    tar -xzf /tmp/install-tl-unx.tar.gz -C /tmp/install-tl --strip-components=1; \
    perl /tmp/install-tl/install-tl \
        --no-interaction \
        --scheme=small \
        --no-doc-install \
        --no-src-install \
        --location "$MIRROR/"; \
    TEXBIN="$(dirname "$(find /usr/local/texlive \( -type f -o -type l \) -name tlmgr -print -quit)")"; \
    test -n "$TEXBIN"; \
    ln -sfn "$TEXBIN" /opt/texlive-bin; \
    /opt/texlive-bin/tlmgr install \
        latexmk \
        titlesec \
        newtx \
        fontaxes \
        booktabs \
        caption \
        hyperref \
        geometry \
        natbib \
        amsmath \
        tools \
        graphics; \
    rm -rf /tmp/install-tl /tmp/install-tl-unx.tar.gz

ENV PATH="/opt/texlive-bin:${PATH}"
USER vscode
