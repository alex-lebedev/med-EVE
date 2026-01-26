# Aletheia Local Demo Runner (Windows)

Write-Host "Starting Aletheia Demo..."

# Set environment
$env:PYTHONPATH = "$PWD\backend"

# Start backend
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"

Write-Host "Backend started on http://localhost:8000"

# Frontend placeholder

Write-Host "Demo running. Check http://localhost:8000/health"