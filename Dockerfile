FROM python:3.9-slim-bookworm

ARG PIP_INDEX_URL=""
ARG APT_MIRROR=""
ARG HTTPS_PROXY=""
ARG NO_PROXY=""

# Dependencies needed mostly by pywikibot
ENV DEBIAN_FRONTEND=noninteractive
RUN if [ -n "$APT_MIRROR" ]; then \
        echo "deb $APT_MIRROR/debian bookworm main contrib non-free" > /etc/apt/sources.list && \
        echo "deb $APT_MIRROR/debian bookworm-updates main contrib non-free" >> /etc/apt/sources.list && \
        echo "deb $APT_MIRROR/debian-security bookworm-security main contrib non-free" >> /etc/apt/sources.list && \
        # Debian repositories with frequent updates e.g.,
        # ${distro}-security, ${distro}-updates, and ${distro}-backports
        # have a short (one week) Valid-Until expiry
        # which conflicts with our practice of a local apt-mirror updating weekly
        echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until && \
        apt update -o Dir::Etc::sourcelist="sources.list" -o Dir::Etc::sourceparts="-" -o APT::Get::List-Cleanup="0"; \
    else \
        apt update; \
    fi && apt install -y \
        git \
        expect \
        curl

WORKDIR /app

# Needed for pywikibot
RUN pip install --upgrade setuptools

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
