FROM alpine:3.15
MAINTAINER @Lordslair

RUN adduser -h /code -u 1000 -D -H websocket

ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

COPY                             requirements.txt /requirements.txt
COPY --chown=websocket:websocket websocket.py     /code/websocket.py

RUN apk update --no-cache \
    && apk add --no-cache python3 py3-pip \
    && apk add --no-cache --virtual .build-deps \
                                    gcc \
                                    libc-dev \
                                    libffi-dev \
                                    python3-dev \
                                    tzdata \
    && pip3 --no-cache-dir install -U -r /requirements.txt \
    && cp /usr/share/zoneinfo/Europe/Paris /etc/localtime \
    && cd /code \
    && su websocket -c "pip install --user -U -r /requirements.txt" \
    && apk del .build-deps \
    && rm /requirements.txt

USER websocket
WORKDIR /code
ENV PATH="/code/.local/bin:${PATH}"

ENTRYPOINT ["/code/websocket.py"]
