#!/bin/bash
# Quickstart script - test the agent API

set -e

echo "=== CAD-MATLAB Agent Quickstart ==="
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Run: cp .env.example .env"
    echo "Then edit .env and add OPENROUTER_API_KEY"
    exit 1
fi

# Check if OPENROUTER_API_KEY is set
source .env
if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "Error: OPENROUTER_API_KEY not set in .env"
    exit 1
fi

echo "✓ Environment configured"
echo ""

# Start API server in background
echo "Starting API server..."
python -m uvicorn agent.api.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Check health
echo ""
echo "Checking health..."
curl -s http://localhost:8000/health | python -m json.tool

# Send test chat message
echo ""
echo ""
echo "Sending test design request..."
echo ""

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Design a simple rectangular enclosure. Start with 100x50x30mm dimensions.",
    "run_id": null
  }' | python -m json.tool

echo ""
echo ""
echo "=== Test Complete ==="
echo ""
echo "API is running at http://localhost:8000"
echo "Docs: http://localhost:8000/docs"
echo ""
echo "To stop the server: kill $API_PID"
echo "Or press Ctrl+C"
echo ""

# Keep script running
wait $API_PID

