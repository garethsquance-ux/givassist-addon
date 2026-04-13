ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3

RUN mkdir -p /app /etc/services.d/givassist

COPY rootfs/app/ /app/
COPY server.py /server.py

# Create s6 service scripts inline to guarantee Unix line endings
# (Windows git can corrupt line endings in COPY'd files)
RUN printf '#!/usr/bin/with-contenv bashio\nbashio::log.info "Starting GivAssist Wizard..."\nexec python3 /server.py\n' > /etc/services.d/givassist/run \
    && printf '#!/usr/bin/env bashio\ndeclare APP_EXIT_CODE=${1}\nif [[ "${APP_EXIT_CODE}" -ne 0 ]] && [[ "${APP_EXIT_CODE}" -ne 256 ]]; then\n  bashio::log.warning "GivAssist exited with code ${APP_EXIT_CODE}"\n  echo "${APP_EXIT_CODE}" > /run/s6-linux-init-container-results/exitcode\n  exec /run/s6/basedir/bin/halt\nfi\n' > /etc/services.d/givassist/finish \
    && chmod a+x /etc/services.d/givassist/run /etc/services.d/givassist/finish
