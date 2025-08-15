#!/bin/bash
# run_mcp_sse.sh

WORKDIR="${1:-$(pwd)}" # Default to current directory if no argument is provided

echo "[run_mcp_sse] Stopping Docker Compose services..."
docker compose -f "$WORKDIR/docker-compose-mcp-sse.yml" down
