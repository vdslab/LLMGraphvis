#!/bin/bash
# Docker build script with optimized settings

# Enable BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

echo "🚀 Starting optimized Docker build..."
echo "BuildKit: Enabled"
echo ""

# Show build start time
START_TIME=$(date +%s)

# Build with docker compose
docker compose build "$@"

# Calculate and show build time
END_TIME=$(date +%s)
BUILD_TIME=$((END_TIME - START_TIME))

echo ""
echo "✅ Build completed in ${BUILD_TIME} seconds"
