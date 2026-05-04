FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    python3-dev \
    libssl-dev \
    libffi-dev \
    libkrb5-dev \
    libsasl2-dev \
    libldap2-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpq-dev \
    curl \
    wget \
    git \
    sshpass \
    net-tools \
    iputils-ping \
    && apt-get clean

# Create virtual env
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements
COPY requirements.txt .

# Install python deps
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

CMD ["/bin/bash"]
