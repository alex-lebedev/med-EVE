# Troubleshooting UI Issues

## The UI Should Have These Buttons

In the header (top bar), you should see:
1. **🎬 Demo Mode** button (left side)
2. **Case:** dropdown selector
3. **Load** button (next to the dropdown)

## If You Don't See the Buttons

### Solution 1: Clear Browser Cache

**Chrome/Edge:**
1. Press `Cmd+Shift+Delete` (Mac) or `Ctrl+Shift+Delete` (Windows)
2. Select "Cached images and files"
3. Click "Clear data"
4. Refresh the page (`Cmd+R` or `Ctrl+R`)

**Or Hard Refresh:**
- Mac: `Cmd+Shift+R`
- Windows: `Ctrl+Shift+R`

### Solution 2: Check Browser Console

1. Open Developer Tools: `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)
2. Go to "Console" tab
3. Look for any red error messages
4. Share the errors if you see any

### Solution 3: Verify Backend is Running

```bash
# Check if backend is running
curl http://localhost:8000/health

# Should return something like:
# {"model_loaded": false, "device": "cpu", "lite_mode": true, ...}
```

If you get a connection error, restart the backend:
```bash
make stop
make run
```

### Solution 4: Check the URL

Make sure you're accessing:
- `http://localhost:8080/index.html` (frontend)
- NOT `http://localhost:8000` (that's the backend API)

### Solution 5: Restart Everything

```bash
# Stop all servers
make stop

# Wait a few seconds, then restart
make demo
```

## How to Use the UI

### Method 1: Use the "Load" Button

1. Select a case from the dropdown (e.g., `case_01_iron_deficiency_anemia`)
2. Click the **"Load"** button
3. The case will run automatically

### Method 2: Use "Demo Mode" Button

1. Click **"🎬 Demo Mode"** button
2. This automatically loads and runs the gotcha case

### Method 3: Use URL Parameters

Add to the URL:
```
http://localhost:8080/index.html?case=case_01_iron_deficiency_anemia&autoplay=true
```

This will:
- Load the specified case
- Auto-play the animation

## What You Should See

After clicking "Load" or "Demo Mode":

1. **Timeline** (top): Shows pipeline steps (Lab Normalize, Context Select, etc.)
2. **Left Panel**: Shows abnormal labs
3. **Center**: Knowledge graph visualization
4. **Right Panel**: 
   - "Clinician" tab: Shows hypotheses
   - "Patient" tab: Shows patient actions
5. **Playback Controls**: Play/Pause/Replay buttons in the timeline

## Common Issues

### Issue: "Loading case..." never finishes

**Check:**
1. Backend is running: `curl http://localhost:8000/health`
2. No CORS errors in browser console
3. Backend logs show the request

**Fix:**
```bash
# Restart backend
make stop
make run
```

### Issue: Buttons are there but don't work

**Check browser console for JavaScript errors**

**Fix:**
- Clear cache (see Solution 1 above)
- Hard refresh the page

### Issue: Graph doesn't show

**Check:**
- Browser console for Cytoscape errors
- Network tab to see if files are loading

**Fix:**
- Make sure you have internet (Cytoscape loads from CDN)
- Or check if `https://unpkg.com/cytoscape@3.23.0/dist/cytoscape.min.js` is accessible

### Issue: Cases dropdown is empty

**Check:**
- Backend is running
- API endpoint works: `curl http://localhost:8000/cases`

**Fix:**
- Restart backend
- Check backend logs for errors

### Issue: Model errors on Apple Silicon (MPS / "Placeholder storage has not been allocated")

On Apple Silicon (M1/M2/M3), the app uses CPU by default for reliability. If you see MPS-related errors or hypotheses not generated, force CPU: `export MEDGEMMA_DEVICE=cpu` before starting the backend. To try MPS instead, set `export USE_MPS=1`.

### Testing model text generation (CPU vs MPS)

To confirm the model can generate text at all (e.g. before debugging "Loading case..." or empty hypotheses), run from repo root:

- **CPU:** `MEDGEMMA_DEVICE=cpu make model-test` or `MODE=model python scripts/test_model_generate.py --device cpu`
- **MPS:** `USE_MPS=1 make model-test` or `MODE=model python scripts/test_model_generate.py --device mps`

Expect: model load (30–60+ s), then "Generated: '...'" and "OK: Model generated text." If it hangs or fails, the issue is device/runtime or model output.

### Why does the first case take so long?

In model mode, each case runs several model calls (hypothesis generation, often action generation, case impression, and sometimes context selection, symptom mapping, evidence weighting, test recommendation, guardrail explanation). Pipeline agents use **max_tokens=384** by default (configurable via `MEDGEMMA_MAX_TOKENS`) so runs complete reliably on laptop/MPS. Expect **2–5+ minutes per case** on a laptop (CPU or MPS), especially the first case. The simple `make model-test` runs only one short generation (64 tokens), so it finishes quickly after load.

To reduce model calls further while keeping graph updates and hypotheses: set `USE_SYMPTOM_MAPPER_MODEL=0` (rule-based symptom mapping) and/or `USE_CASE_IMPRESSION_MODEL=0` (rule-based case impression). By default, context selection, evidence weighting, test recommendation, and guardrail explanation are **disabled**; enable with:
- `USE_CONTEXT_SELECTION_MODEL=1`
- `USE_EVIDENCE_WEIGHTING_MODEL=1`
- `USE_TEST_RECOMMENDATION_MODEL=1`
- `USE_GUARDRAIL_EXPLANATION_MODEL=1`

Novel insights are generated only when `USE_NOVEL_INSIGHT_MODEL=1` (or `force`), and will be labeled "Outside KG" in the UI.

Response fields added for novelty:
- `reasoner_output.novel_insights`
- `reasoner_output.novel_actions`
- `reasoner_output.provenance`

### Backend port and debug endpoints

The backend should run on **127.0.0.1:8000** (the frontend uses `http://localhost:8000`). Debug endpoints:

- `POST /debug/ping` — verifies POSTs reach the backend.
- `POST /debug/raw-run` — echoes raw request body preview to confirm JSON parsing.

Stability flags to use during troubleshooting:

- `MEDGEMMA_MAX_TOKENS=384`
- `USE_SYMPTOM_MAPPER_MODEL=0`
- `USE_CASE_IMPRESSION_MODEL=0`
- `USE_CONTEXT_SELECTION_MODEL=0`
- `USE_EVIDENCE_WEIGHTING_MODEL=0`
- `USE_TEST_RECOMMENDATION_MODEL=0`
- `USE_GUARDRAIL_EXPLANATION_MODEL=0`
- `USE_NOVEL_INSIGHT_MODEL=0`

## Still Having Issues?

1. **Check backend logs:**
   ```bash
   # If running with make demo, check:
   tail -f /tmp/backend.log
   ```

2. **Check frontend logs:**
   ```bash
   tail -f /tmp/frontend.log
   ```

3. **Try API directly:**
   ```bash
   curl -X POST "http://localhost:8000/run" \
     -H "Content-Type: application/json" \
     -d '{"case_id": "case_01_iron_deficiency_anemia"}'
   ```

4. **Share:**
   - Browser console errors
   - Backend logs
   - What you see vs. what you expect
