#!/bin/bash
# run_in_copilot.sh

WORKDIR="${1:-$(pwd)}" # Default to current directory if no argument is provided

echo "[run_in_copilot] A working directory be used: $WORKDIR"

# docker-compose -f "$WORKDIR/docker-compose-mcp.yml" --env-file .env up -d

uv --directory "$WORKDIR/mcp-server" run minima
