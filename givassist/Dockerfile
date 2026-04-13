ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache nginx

RUN mkdir -p /app /run/nginx /var/lib/nginx /var/log/nginx

COPY rootfs/ /

RUN chmod +x /etc/services.d/givassist/run

ENTRYPOINT ["/init"]
