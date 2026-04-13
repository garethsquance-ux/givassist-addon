#!/usr/bin/with-contenv bashio

# Get the HA token for API proxying
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"

bashio::log.info "Starting GivAssist Wizard..."
bashio::log.info "Access via the sidebar or http://localhost:8099"

# Substitute the supervisor token into nginx config
envsubst '${SUPERVISOR_TOKEN}' < /etc/nginx/http.d/default.conf > /tmp/nginx.conf
mv /tmp/nginx.conf /etc/nginx/http.d/default.conf

# Start nginx
exec nginx -g 'daemon off;'
