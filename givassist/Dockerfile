ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache nginx

RUN mkdir -p /app /run/nginx /var/lib/nginx /var/log/nginx

COPY rootfs/app/ /app/
COPY nginx.conf /etc/nginx/http.d/default.conf
COPY run.sh /run.sh
RUN chmod +x /run.sh

# Remove default nginx config that might conflict
RUN rm -f /etc/nginx/http.d/default.conf.bak 2>/dev/null; true

CMD ["/run.sh"]
