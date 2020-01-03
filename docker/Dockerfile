FROM python:3.7-buster as builder

ARG REPO=rsksmart/lumino
ARG LUMINO_VERSION=releases/0.0.4

RUN apt update
RUN apt install software-properties-common -y
RUN apt-get install libpq-dev python3.7-dev virtualenv -y

ADD https://api.github.com/repos/${REPO}/commits/${LUMINO_VERSION} /dev/null

RUN git clone -b ${LUMINO_VERSION} https://github.com/${REPO} /app/lumino --depth 1

RUN ls /app/lumino

RUN apt install libsecp256k1-dev -y

RUN apt-get install libssl-dev build-essential automake pkg-config libtool libffi-dev libgmp-dev libyaml-cpp-dev -y

WORKDIR /app/lumino

RUN virtualenv -p /usr/local/bin/python3.7 clientEnv

RUN . clientEnv/bin/activate

RUN pip install -r requirements.txt -c constraints.txt -e .

RUN python setup.py develop

#RUN lumino

RUN apt install expect -y

COPY ./run.exp /app/lumino/

COPY ./start.sh /app/lumino

RUN chmod +x /app/lumino/run.exp /app/lumino/start.sh

RUN wget https://gethstore.blob.core.windows.net/builds/geth-linux-amd64-1.9.9-01744997.tar.gz

RUN tar -zxvf geth-linux-amd64-1.9.9-01744997.tar.gz

RUN rm geth-linux-amd64-1.9.9-01744997.tar.gz

RUN mv geth-linux-amd64-1.9.9-01744997/geth ./ && chmod +x geth

RUN rm -rf geth-linux-amd64-1.9.9-01744997

#RUN export PASS=12345

RUN echo "12345" > ./passwd

CMD ./geth account new --password ./passwd

CMD ls /root/.ethereum/keystore

ENTRYPOINT "/app/lumino/start.sh"

#ENTRYPOINT ["lumino"]

#--------------------------------
#FROM python:3.7-slim as runner

#COPY --from=builder /opt/venv /opt/venv

#WORKDIR /opt/venv

#RUN ls /opt/venv/bin

#ENTRYPOINT ["/opt/venv/bin/python3","lumino"]




