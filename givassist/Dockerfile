ARG BUILD_FROM
FROM ${BUILD_FROM}

# Install nginx and envsubst
RUN apk add --no-cache nginx gettext

# Create app directory
RUN mkdir -p /app

# Copy the built wizard files
COPY rootfs/app /app

# Copy nginx config
COPY nginx.conf /etc/nginx/http.d/default.conf

# Create nginx directories
RUN mkdir -p /run/nginx /var/log/nginx

# Copy the run script
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
