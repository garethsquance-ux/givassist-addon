ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3

RUN mkdir -p /app /etc/services.d/givassist

COPY rootfs/app/ /app/
COPY server.py /server.py

# Create the s6 service run script inline (avoids Windows line ending issues)
RUN printf '#!/usr/bin/with-contenv bashio\nbashio::log.info "Starting GivAssist Wizard on port 8099..."\nexec python3 /server.py\n' > /etc/services.d/givassist/run \
    && chmod +x /etc/services.d/givassist/run
