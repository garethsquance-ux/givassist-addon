ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install nginx to serve the wizard
RUN apk add --no-cache nginx

# Copy the built wizard
COPY rootfs /

# Copy nginx config
COPY nginx.conf /etc/nginx/http.d/default.conf

# Copy the run script
COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
