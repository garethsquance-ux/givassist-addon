ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3

RUN mkdir -p /app

COPY rootfs/ /
COPY server.py /server.py

RUN chmod a+x /etc/services.d/givassist/run /etc/services.d/givassist/finish
