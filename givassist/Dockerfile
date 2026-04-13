ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache nginx

RUN mkdir -p /app /run/nginx

COPY rootfs/app /app
COPY nginx.conf /etc/nginx/http.d/default.conf
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
