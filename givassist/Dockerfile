ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3

RUN mkdir -p /app /etc/services.d/givassist

COPY rootfs/app/ /app/
COPY server.py /server.py

RUN printf '#!/usr/bin/with-contenv sh\nexec python3 /server.py\n' > /etc/services.d/givassist/run && chmod +x /etc/services.d/givassist/run
