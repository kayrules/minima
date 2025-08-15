#!/bin/bash
# run_mcp_sse.sh

WORKDIR="${1:-$(pwd)}" # Default to current directory if no argument is provided

echo "[run_mcp_sse] A working directory be used: $WORKDIR"

# Create necessary directories if they don't exist
echo "[run_mcp_sse] Creating necessary directories..."
mkdir -p "$WORKDIR/qdrant_data"
mkdir -p "$WORKDIR/indexer_data"
mkdir -p "$WORKDIR/cache/huggingface"
mkdir -p "$WORKDIR/cache/nltk"
chmod 755 "$WORKDIR/qdrant_data"
chmod 755 "$WORKDIR/indexer_data"
chmod 755 "$WORKDIR/cache/huggingface"
chmod 755 "$WORKDIR/cache/nltk"

echo "[run_mcp_sse] Starting Docker Compose services..."
docker-compose -f "$WORKDIR/docker-compose-mcp-sse.yml" --env-file .env up -d

echo "[run_mcp_sse] Starting MCP server..."
uv --directory "$WORKDIR/mcp-server" run minima
