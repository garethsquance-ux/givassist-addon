ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3

RUN mkdir -p /app

COPY rootfs/app/ /app/
COPY server.py /server.py
