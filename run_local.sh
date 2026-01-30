#!/bin/bash

# med-EVE Local Demo Runner

echo "Starting med-EVE Demo..."

# Set environment
export PYTHONPATH=$PWD

# Start backend
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Backend started on http://localhost:8000"

# Start frontend (placeholder, assume npm installed)
# cd ../frontend
# npm install
# npm run dev &
# FRONTEND_PID=$!

echo "Frontend placeholder - backend API ready"

# Open browser to backend health or something
sleep 2
# open http://localhost:8000/health

echo "Demo running. Press Ctrl+C to stop."

# Wait
wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true