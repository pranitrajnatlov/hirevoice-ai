#!/bin/bash

# Ensure we are in the project root
cd "$(dirname "$0")"

echo "Stopping services..."

if [ -f .ai.pid ]; then
  kill $(cat .ai.pid) 2>/dev/null
  rm .ai.pid
  echo "Stopped AI Service."
fi

if [ -f .gateway.pid ]; then
  kill $(cat .gateway.pid) 2>/dev/null
  rm .gateway.pid
  echo "Stopped Gateway Service."
fi

if [ -f .web.pid ]; then
  kill $(cat .web.pid) 2>/dev/null
  rm .web.pid
  echo "Stopped Web Service."
fi

# Fallback cleanup to ensure no orphaned processes remain
pkill -f "uvicorn services.ai.app.main:app" 2>/dev/null || true
pkill -f "uvicorn services.gateway.app.main:app" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true

echo "All services stopped successfully."
