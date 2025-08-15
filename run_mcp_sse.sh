#!/bin/bash
# run_mcp_sse.sh

WORKDIR="${1:-$(pwd)}" # Default to current directory if no argument is provided

echo "[run_mcp_sse] A working directory be used: $WORKDIR"

# Create necessary directories if they don't exist (only for bind mounts)
echo "[run_mcp_sse] Creating necessary directories..."
mkdir -p "$WORKDIR/qdrant_data"
mkdir -p "$WORKDIR/indexer_data"
chmod 755 "$WORKDIR/qdrant_data"
chmod 755 "$WORKDIR/indexer_data"

echo "[run_mcp_sse] Starting Docker Compose services..."
docker compose -f "$WORKDIR/docker-compose-mcp-sse.yml" --env-file .env up -d

echo "[run_mcp_sse] Services started successfully!"
echo "[run_mcp_sse] - Indexer: http://localhost:8002"
echo "[run_mcp_sse] - SSE Server: http://localhost:8003"
echo "[run_mcp_sse] Check status: docker compose -f docker-compose-mcp-sse.yml ps"
