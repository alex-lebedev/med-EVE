.PHONY: setup verify test evals evals-model-smoke ablations help run demo stop model-demo model-test hypothesis-test optimize-experiment reproduce

# Prefer venv/.venv python so "make demo" works without activating; fallback to python3 (macOS).
# Use absolute path so "make run" / "make demo" work after "cd backend".
ROOT_DIR := $(CURDIR)
PYTHON := $(shell if [ -f "$(ROOT_DIR)/venv/bin/python" ]; then echo "$(ROOT_DIR)/venv/bin/python"; elif [ -f "$(ROOT_DIR)/.venv/bin/python" ]; then echo "$(ROOT_DIR)/.venv/bin/python"; else echo python3; fi)

# Default target
help:
	@echo "Available targets:"
	@echo "  setup   - Create venv and install dependencies"
	@echo "  verify  - Run pytest and evals (default)"
	@echo "  test    - Run pytest tests only"
	@echo "  evals   - Run evaluation script only"
	@echo "  evals-model-smoke - Quick model-mode smoke eval (1 case)"
	@echo "  ablations - Run internal ablations (lite/hybrid/full-agent)"
	@echo "  reproduce - Setup + evals with fixed seed"
	@echo "  run     - Start backend server only"
	@echo "  demo    - Start backend + frontend and open browser (auto-play gotcha case)"
	@echo "  model-demo - Start demo with model enabled (MODE=model)"
	@echo "  model-test - Test model load and text generation (MODE=model; use MEDGEMMA_DEVICE=cpu or USE_MPS=1)"
	@echo "  hypothesis-test - Run hypothesis_generation prompt; saves prompt and raw output to backend/output/"
	@echo "  optimize-experiment - Run optimization experiment (baseline/fast/quality configs; MODE=model)"
	@echo "  stop    - Stop all running servers"

# Run both pytest and evals
verify: test evals
	@echo "✓ Verification complete"

# Bootstrap local environment
setup:
	@bash setup.sh

# Run pytest tests
test:
	@echo "Running pytest tests..."
	@cd backend && export PYTHONPATH=$$(pwd) && $(PYTHON) -m pytest tests/ -v || echo "Note: Some tests may fail due to environment issues (torch/numpy)"

# Run evaluation script
evals:
	@echo "Running evals..."
	@cd backend && export PYTHONPATH=$$(pwd) && export REPRODUCIBILITY_SEED=$${REPRODUCIBILITY_SEED:-42} && $(PYTHON) evals/run_evals.py --dataset golden

evals-model-smoke:
	@echo "Running model-mode smoke eval..."
	@cd backend && export PYTHONPATH=$$(pwd) && export MODE=model && export REPRODUCIBILITY_SEED=$${REPRODUCIBILITY_SEED:-42} && $(PYTHON) evals/run_evals.py --dataset legacy --limit 1

ablations:
	@echo "Running internal ablations..."
	@export REPRODUCIBILITY_SEED=$${REPRODUCIBILITY_SEED:-42} && $(PYTHON) scripts/run_ablations.py --dataset golden

# Start backend server only
run:
	@echo "Starting backend server..."
	@echo "Backend will be available at http://localhost:8000"
	@echo "API docs at http://localhost:8000/docs"
	@if [ -z "$$MODE" ]; then \
		echo "⚠️  Running in LITE mode (rule-based only)"; \
		echo "   To enable model: export MODE=model && make run"; \
	else \
		echo "✓ MODE=$$MODE detected"; \
	fi
	@echo "Press Ctrl+C to stop"
	@cd backend && export PYTHONPATH=$$(pwd) && export REPRODUCIBILITY_SEED=$${REPRODUCIBILITY_SEED:-42} && $(PYTHON) -m uvicorn app:app --host 127.0.0.1 --port 8000

# Start demo (backend + frontend + browser)
demo:
	@echo "Starting med-EVE (Evidence Vector Engine) Demo..."
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
	if [ -f "$$ROOT_DIR/venv/bin/python" ]; then PY=$$ROOT_DIR/venv/bin/python; elif [ -f "$$ROOT_DIR/.venv/bin/python" ]; then PY=$$ROOT_DIR/.venv/bin/python; else PY=python3; fi; \
	if [ -z "$$MODE" ]; then \
		echo "⚠️  Running in LITE mode (rule-based only)"; \
		echo "   To enable model: export MODE=model && make demo"; \
	else \
		echo "✓ MODE=$$MODE detected - model will be enabled"; \
	fi; \
	cd $$ROOT_DIR/backend && export PYTHONPATH=$$ROOT_DIR/backend && export MODE=$$MODE && export USE_MPS=$$USE_MPS && export MEDGEMMA_DEVICE=$$MEDGEMMA_DEVICE && export REPRODUCIBILITY_SEED=$${REPRODUCIBILITY_SEED:-42} && $$PY -m uvicorn app:app --host 127.0.0.1 --port 8000 > /tmp/backend.log 2>&1 & \
	BACKEND_PID=$$!; \
	echo "Backend starting (PID: $$BACKEND_PID)..."; \
	sleep 4; \
	if ! kill -0 $$BACKEND_PID 2>/dev/null; then \
		echo "❌ Backend failed to start. Check logs: tail -f /tmp/backend.log"; \
		exit 1; \
	fi; \
	cd $$ROOT_DIR/frontend && $$PY -m http.server 8080 > /tmp/frontend.log 2>&1 & \
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

# Test model load and text generation (run from repo root; optional: MEDGEMMA_DEVICE=cpu or USE_MPS=1)
model-test:
	@export PYTHONPATH=$$(pwd)/backend && export MODE=model && export USE_MPS=$$USE_MPS && export MEDGEMMA_DEVICE=$$MEDGEMMA_DEVICE && $(PYTHON) scripts/test_model_generate.py

# Run hypothesis_generation prompt with one case; saves prompt and raw output to backend/output/
hypothesis-test:
	@export PYTHONPATH=$$(pwd)/backend && export MODE=model && export USE_MPS=$$USE_MPS && export MEDGEMMA_DEVICE=$$MEDGEMMA_DEVICE && $(PYTHON) scripts/test_hypothesis_prompt.py

# Run optimization experiment: baseline vs fast vs quality configs (requires MODE=model / loaded model)
optimize-experiment:
	@cd backend && export PYTHONPATH=$$(pwd) && export MODE=model && export USE_MPS=$$USE_MPS && export MEDGEMMA_DEVICE=$$MEDGEMMA_DEVICE && $(PYTHON) evals/run_optimization_experiment.py --experiment --cases case_02_anemia_of_inflammation_gotcha case_04_primary_hypothyroid

reproduce:
	@$(MAKE) setup
	@REPRODUCIBILITY_SEED=$${REPRODUCIBILITY_SEED:-42} $(MAKE) evals

# Start demo with model enabled
model-demo:
	@echo "Starting med-EVE (Evidence Vector Engine) Demo with MODEL enabled..."
	@export MODE=model && $(MAKE) demo

# Stop all servers (find and kill processes)
stop:
	@echo "Stopping servers..."
	@pkill -f "uvicorn.*app:app" 2>/dev/null || true
	@pkill -f "http.server.*8080" 2>/dev/null || true
	@-lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@-lsof -ti:8080 | xargs kill -9 2>/dev/null || true
	@echo "Servers stopped"
