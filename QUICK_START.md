# Quick Start Guide

## For Demo Recording (2 minutes)

1. **Clone and setup** (30 seconds):
   ```bash
   git clone <repo-url>
   cd aletheia-demo
   pip install fastapi uvicorn pydantic pyyaml
   ```

2. **Run demo** (10 seconds):
   ```bash
   make demo
   ```

3. **Record** (90 seconds):
   - Browser opens automatically to gotcha case
   - Demo auto-plays
   - Follow DEMO_SCRIPT.md for narration

That's it! The demo is ready to record.

## Manual Commands

- `make run` - Start backend only
- `make demo` - Start backend + frontend + open browser
- `make stop` - Stop all servers
- `make verify` - Run tests

## Troubleshooting

- **Backend not starting**: Check port 8000 is free
- **Frontend not loading**: Check port 8080 is free
- **Browser not opening**: Manually open http://localhost:8080/index.html?case=case_02_anemia_of_inflammation_gotcha&autoplay=true
