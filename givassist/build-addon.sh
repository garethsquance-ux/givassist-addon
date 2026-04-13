#!/bin/bash
# Build the GivAssist addon
# Run from the givassist-wizard root directory:
#   bash addon/givassist/build-addon.sh

set -e

echo "Building GivAssist wizard..."
npm run build

echo "Copying built wizard into addon..."
rm -rf addon/givassist/rootfs/app
mkdir -p addon/givassist/rootfs/app
cp -r dist/* addon/givassist/rootfs/app/

echo "Addon ready at addon/givassist/"
echo "To test locally: docker build -t givassist-addon --build-arg BUILD_FROM=ghcr.io/home-assistant/amd64-base:latest addon/givassist/"
echo ""
echo "To publish: push addon/givassist/ to a GitHub repository"
echo "Then users add your repo URL in HA → Settings → Add-ons → Repositories"
