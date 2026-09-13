#!/usr/bin/env bash
# scripts/generate_client.sh
# Generates a TypeScript frontend client from the Gateway/Mission OpenAPI spec (P1-16).
# 
# Pre-requisite: The FastAPI gateway must be running on localhost:8000
# and `npx` must be available.

set -e

echo "Ensuring target directory exists..."
mkdir -p apps/web/lib/api

echo "Downloading OpenAPI spec from Gateway..."
# You can also run `python -c "from services.gateway.implementation import app; import json; print(json.dumps(app.openapi()))"`
# to generate it offline, but fetching it live guarantees accuracy of the mounted routers.
curl -s http://localhost:8000/openapi.json -o /tmp/satquery_openapi.json

echo "Generating TypeScript client..."
npx openapi-typescript-codegen --input /tmp/satquery_openapi.json --output apps/web/lib/api --client axios

echo "Done! Client generated in apps/web/lib/api"
