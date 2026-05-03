#!/bin/bash
# deployment/start.sh – Start both backend and frontend services

set -e

echo "🚀 Starting Election Guide Assistant..."

# Start FastAPI backend in background
uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info &

BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready
echo "⏳ Waiting for backend..."
sleep 5

# Start Streamlit frontend
streamlit run frontend/streamlit_app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false &

FRONTEND_PID=$!
echo "✅ Frontend started (PID: $FRONTEND_PID)"

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
