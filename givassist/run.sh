#!/bin/sh
echo "=== GivAssist Wizard Starting ==="
echo "Checking files..."
ls -la /app/
echo "Starting nginx on port 8099..."
exec nginx -g 'daemon off; error_log stderr info;'
