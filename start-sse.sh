#!/bin/bash

WORKDIR="${1:-$(pwd)}"

# rm -rf qdrant_data/ indexer_data/
docker-compose -f "$WORKDIR/docker-compose-mcp-sse.yml" up -d