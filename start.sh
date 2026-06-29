#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Cassandra..."
docker compose -f DataBase/docker-compose.unicus.yml up -d cassandra
echo "Waiting 30s for Cassandra to be ready..."
sleep 30
echo "Starting Unicus Backend..."
cd DataBase && python -m unicus_lims
