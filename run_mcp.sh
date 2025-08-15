#!/bin/bash
# run_mcp.sh

WORKDIR="${1:-$(pwd)}" # Default to current directory if no argument is provided

echo "[run_mcp] A working directory be used: $WORKDIR"

# Create necessary directories if they don't exist
echo "[run_mcp] Creating necessary directories..."
mkdir -p "$WORKDIR/qdrant_data"
mkdir -p "$WORKDIR/indexer_data"
chmod 755 "$WORKDIR/qdrant_data"
chmod 755 "$WORKDIR/indexer_data"

echo "[run_mcp] Starting Docker Compose services..."
docker-compose -f "$WORKDIR/docker-compose-mcp.yml" --env-file .env up -d --build

echo "[run_mcp] Starting MCP server..."
uv --directory "$WORKDIR/mcp-server" run minima
