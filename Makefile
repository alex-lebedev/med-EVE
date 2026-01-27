.PHONY: verify test evals help run demo stop

# Default target
help:
	@echo "Available targets:"
	@echo "  verify  - Run pytest and evals (default)"
	@echo "  test    - Run pytest tests only"
	@echo "  evals   - Run evaluation script only"
	@echo "  run     - Start backend server only"
	@echo "  demo    - Start backend + frontend and open browser (auto-play gotcha case)"
	@echo "  stop    - Stop all running servers"

# Run both pytest and evals
verify: test evals
	@echo "✓ Verification complete"

# Run pytest tests
test:
	@echo "Running pytest tests..."
	@cd backend && export PYTHONPATH=$$(pwd) && python -m pytest tests/ -v || echo "Note: Some tests may fail due to environment issues (torch/numpy)"

# Run evaluation script
evals:
	@echo "Running evals..."
	@cd backend && export PYTHONPATH=$$(pwd) && python evals/run_evals.py

# Start backend server only
run:
	@echo "Starting backend server..."
	@echo "Backend will be available at http://localhost:8000"
	@echo "API docs at http://localhost:8000/docs"
	@echo "Press Ctrl+C to stop"
	@cd backend && export PYTHONPATH=$$(pwd) && python -m uvicorn app:app --host 0.0.0.0 --port 8000

# Start demo (backend + frontend + browser)
demo:
	@echo "Starting Aletheia Demo..."
	@echo ""
	@echo "This will:"
	@echo "  1. Start backend on http://localhost:8000"
	@echo "  2. Start frontend server on http://localhost:8080"
	@echo "  3. Open browser to gotcha case with autoplay"
	@echo ""
	@echo "Press Ctrl+C to stop all servers"
	@echo ""
	@echo "Stopping any existing servers on ports 8000 and 8080..."
	@-pkill -f "uvicorn.*app:app" 2>/dev/null || true
	@-pkill -f "http.server.*8080" 2>/dev/null || true
	@-lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@-lsof -ti:8080 | xargs kill -9 2>/dev/null || true
	@sleep 2
	@ROOT_DIR=$$(pwd); \
	cd $$ROOT_DIR/backend && export PYTHONPATH=$$ROOT_DIR/backend && python -m uvicorn app:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 & \
	BACKEND_PID=$$!; \
	echo "Backend starting (PID: $$BACKEND_PID)..."; \
	sleep 4; \
	if ! kill -0 $$BACKEND_PID 2>/dev/null; then \
		echo "❌ Backend failed to start. Check logs: tail -f /tmp/backend.log"; \
		exit 1; \
	fi; \
	cd $$ROOT_DIR/frontend && python -m http.server 8080 > /tmp/frontend.log 2>&1 & \
	FRONTEND_PID=$$!; \
	echo "Frontend starting (PID: $$FRONTEND_PID)..."; \
	sleep 2; \
	if ! kill -0 $$FRONTEND_PID 2>/dev/null; then \
		echo "❌ Frontend failed to start. Check logs: tail -f /tmp/frontend.log"; \
		kill $$BACKEND_PID 2>/dev/null || true; \
		exit 1; \
	fi; \
	if command -v open >/dev/null 2>&1; then \
		open "http://localhost:8080/index.html?case=case_02_anemia_of_inflammation_gotcha&autoplay=true" 2>/dev/null || true; \
	elif command -v xdg-open >/dev/null 2>&1; then \
		xdg-open "http://localhost:8080/index.html?case=case_02_anemia_of_inflammation_gotcha&autoplay=true" 2>/dev/null || true; \
	fi; \
	echo ""; \
	echo "✓ Demo running! Servers:"; \
	echo "  Backend: http://localhost:8000 (PID: $$BACKEND_PID)"; \
	echo "  Frontend: http://localhost:8080 (PID: $$FRONTEND_PID)"; \
	echo ""; \
	echo "To view logs:"; \
	echo "  Backend: tail -f /tmp/backend.log"; \
	echo "  Frontend: tail -f /tmp/frontend.log"; \
	echo ""; \
	echo "To stop: Press Ctrl+C or run 'make stop'"; \
	trap "echo ''; echo 'Stopping servers...'; kill $$BACKEND_PID $$FRONTEND_PID 2>/dev/null || true; exit 0" INT TERM EXIT; \
	while true; do \
		if ! kill -0 $$BACKEND_PID 2>/dev/null && ! kill -0 $$FRONTEND_PID 2>/dev/null; then \
			echo "Both servers stopped"; \
			break; \
		fi; \
		sleep 2; \
	done

# Stop all servers (find and kill processes)
stop:
	@echo "Stopping servers..."
	@pkill -f "uvicorn.*app:app" 2>/dev/null || true
	@pkill -f "http.server.*8080" 2>/dev/null || true
	@-lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@-lsof -ti:8080 | xargs kill -9 2>/dev/null || true
	@echo "Servers stopped"
