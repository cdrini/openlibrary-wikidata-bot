FROM ubuntu:bionic

# Dependencies needed mostly by pywikibot
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
    build-essential \
    python3 \
    python3-pip \
    git \
    libssl1.0 \
    libffi-dev \
    expect

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt && \
    # Getting weird SSL verification errors otherwise :/
    pip3 install --upgrade certifi

COPY . .
