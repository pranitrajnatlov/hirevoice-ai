#!/bin/bash

# Ensure we are in the project root
cd "$(dirname "$0")"

echo "Creating log files..."
touch ai.log gateway.log web.log

echo "Starting AI Service (port 8800)..."
.venv/bin/uvicorn services.ai.app.main:app --host 0.0.0.0 --port 8800 --reload > ai.log 2>&1 &
echo $! > .ai.pid

echo "Starting Gateway Service (port 8000)..."
.venv/bin/uvicorn services.gateway.app.main:app --host 0.0.0.0 --port 8000 --reload > gateway.log 2>&1 &
echo $! > .gateway.pid

echo "Starting Web Service (Next.js)..."
cd apps/web
npm run dev > ../../web.log 2>&1 &
echo $! > ../../.web.pid
cd ../..

echo "--------------------------------------------------------"
echo "All services started in the background!"
echo "AI Service Logs:      tail -f ai.log"
echo "Gateway Logs:         tail -f gateway.log"
echo "Web Logs:             tail -f web.log"
echo "--------------------------------------------------------"
echo "Run ./stop.sh to stop all services."
