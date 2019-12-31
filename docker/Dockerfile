FROM python:3.7-buster as builder

ARG REPO=rsksmart/lumino
ARG LUMINO_VERSION=releases/0.0.4

RUN apt update
RUN apt install software-properties-common -y
RUN apt-get install libpq-dev python3.7-dev -y

ADD https://api.github.com/repos/${REPO}/commits/${LUMINO_VERSION} /dev/null

RUN git clone -b ${LUMINO_VERSION} https://github.com/${REPO} /app/lumino --depth 1

RUN ls /app/lumino

RUN apt install libsecp256k1-dev -y

RUN apt-get install libssl-dev build-essential automake pkg-config libtool libffi-dev libgmp-dev libyaml-cpp-dev -y

RUN python3 -m venv /opt/venv

RUN /opt/venv/bin/pip3 install -r /app/lumino/requirements.txt -c /app/lumino/constraints.txt -e /app/lumino

WORKDIR /app/lumino

RUN python3 setup.py develop



