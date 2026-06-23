#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting clipsmith API..."
exec uvicorn clipsmith.api.app:app --host 0.0.0.0 --port 8000 "$@"
