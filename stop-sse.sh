#!/bin/bash

WORKDIR="${1:-$(pwd)}"

docker-compose -f "$WORKDIR/docker-compose-mcp-sse.yml" down